#!/usr/bin/env python3
"""Minimal MCP client for the McDonald's China MCP server (Streamable HTTP).

Protocol: MCP Streamable HTTP transport.
    POST https://mcp.mcd.cn
    Authorization: Bearer <token>
Rate limit: 600 requests/minute per token (429 on exceed).

Usage:
    export MCD_MCP_TOKEN=xxx
    python3 mcp_client.py tools                 # list all tools
    python3 mcp_client.py call order-list '{}'  # call one tool
"""

import json
import os
import sys
import urllib.error
import urllib.request

MCP_URL = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn")
PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "mcd-wrapped", "version": "0.1.0"}


class McpError(RuntimeError):
    pass


class McpClient:
    def __init__(self, token=None, url=None, timeout=30):
        self.token = token or os.environ.get("MCD_MCP_TOKEN")
        if not self.token:
            raise McpError("missing MCP token: set MCD_MCP_TOKEN or pass token=")
        self.url = url or MCP_URL
        self.timeout = timeout
        self.session_id = None
        self._seq = 0

    def _next_id(self):
        self._seq += 1
        return self._seq

    def _post(self, payload, notify=False):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": "Bearer %s" % self.token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
                if sid:
                    self.session_id = sid
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:400]
            except Exception:
                pass
            if e.code == 401:
                raise McpError("HTTP 401: MCP token invalid, expired or missing")
            if e.code == 429:
                raise McpError("HTTP 429: rate limit exceeded (600 req/min)")
            raise McpError("HTTP %s: %s" % (e.code, detail))
        except urllib.error.URLError as e:
            raise McpError("network error: %s" % e.reason)
        if notify or not raw.strip():
            return None
        return self._parse(raw)

    @staticmethod
    def _parse(raw):
        """Accept both plain JSON and SSE-framed responses."""
        if raw.lstrip().startswith("{"):
            try:
                return json.loads(raw)
            except ValueError:
                pass
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if not chunk or chunk == "[DONE]":
                    continue
                try:
                    return json.loads(chunk)
                except ValueError:
                    continue
        return {"raw": raw}

    def initialize(self):
        res = self._post({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
        })
        self._post({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }, notify=True)
        return res

    def list_tools(self):
        res = self._post({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {},
        })
        return (res or {}).get("result", {}).get("tools", [])

    def call_tool(self, name, arguments=None):
        res = self._post({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        })
        if res is None:
            return None
        if "error" in res:
            raise McpError("tool %s error: %s" % (name, res["error"]))
        return (res.get("result") or {}).get("content")


def unwrap(content):
    """Turn MCP tool content into python objects (dict/list/str)."""
    if content is None:
        return None
    texts = []
    for block in content if isinstance(content, list) else [content]:
        if not isinstance(block, dict):
            texts.append(str(block))
            continue
        if block.get("type") == "text":
            texts.append(block.get("text", ""))
        elif "text" in block:
            texts.append(block["text"])
    joined = "\n".join(t for t in texts if t)
    if not joined:
        return None
    try:
        return json.loads(joined)
    except ValueError:
        return joined


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tools"
    client = McpClient()
    client.initialize()
    if cmd == "tools":
        for t in client.list_tools():
            print("%-28s %s" % (t.get("name"), (t.get("description") or "")[:70]))
        return
    if cmd == "call":
        name = sys.argv[2]
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        print(json.dumps(unwrap(client.call_tool(name, args)), ensure_ascii=False, indent=2))
        return
    print(__doc__)


if __name__ == "__main__":
    try:
        main()
    except McpError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        sys.exit(1)
