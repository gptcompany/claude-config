---
name: bytebot
description: Control a containerized Linux desktop via Bytebot API - screenshots, mouse, keyboard, file operations.
homepage: https://github.com/bytebot-ai/bytebot
metadata: {"claude":{"emoji":"🤖","requires":{"mcp":["bytebot"]}}}
---

# Bytebot

Bytebot is a self-hosted AI desktop agent running in a containerized Linux environment.
Use the MCP tools to control the desktop: capture screenshots, move mouse, click, type, scroll, and manage files.

## Available MCP Tools

### Vision
- `computer_screenshot` - Capture current screen (returns base64 PNG)
- `computer_cursor_position` - Get current mouse coordinates

### Mouse Control
- `computer_move_mouse` - Move cursor to coordinates `{x, y}`
- `computer_click_mouse` - Click at position `{coordinates?, button, clickCount, holdKeys?}`
- `computer_press_mouse` - Press/release mouse button `{coordinates?, button, press: "down"|"up"}`
- `computer_drag_mouse` - Drag along path `{path: [{x,y}...], button, holdKeys?}`
- `computer_trace_mouse` - Move along path `{path: [{x,y}...], holdKeys?}`
- `computer_scroll` - Scroll wheel `{coordinates?, direction: "up"|"down"|"left"|"right", scrollCount, holdKeys?}`

### Keyboard Control
- `computer_type_text` - Type text string (< 25 chars, for passwords/forms)
- `computer_paste_text` - Paste text via clipboard (for longer text)
- `computer_type_keys` - Type key sequence (e.g., `["LeftControl", "C"]` for Ctrl+C)
- `computer_press_keys` - Hold/release keys `{keys: [...], press: "down"|"up"}`

### Applications
- `computer_application` - Open/switch app: `firefox`, `vscode`, `terminal`, `1password`, `thunderbird`, `desktop`, `directory`

### File Operations
- `computer_read_file` - Read file from desktop `{path}`
- `computer_write_file` - Write file to desktop `{path, data}` (base64)

### Utility
- `computer_wait` - Pause execution `{duration}` ms

## Valid Keys for type_keys/press_keys

Letters: A-Z
Numbers: Num0-Num9, NumPad0-NumPad9
Function: F1-F24
Modifiers: LeftControl, RightControl, LeftShift, RightShift, LeftAlt, RightAlt, LeftCmd, RightCmd
Navigation: Up, Down, Left, Right, Home, End, PageUp, PageDown
Editing: Backspace, Delete, Insert, Enter, Return, Tab, Space, Escape
Punctuation: Comma, Period, Semicolon, Quote, Backslash, Slash, Minus, Equal, LeftBracket, RightBracket, Grave

## Quickstart

```
# Take a screenshot to see the desktop
computer_screenshot

# Open Firefox
computer_application {application: "firefox"}

# Wait for app to load
computer_wait {duration: 2000}

# Click on URL bar (adjust coordinates based on screenshot)
computer_click_mouse {coordinates: {x: 400, y: 50}, button: "left", clickCount: 1}

# Type a URL
computer_paste_text {text: "https://example.com"}

# Press Enter
computer_type_keys {keys: ["Return"]}
```

## Workflow Pattern

1. **Screenshot first** - Always take a screenshot to understand current state
2. **Identify targets** - Note coordinates of UI elements
3. **Click/interact** - Use coordinates from screenshot
4. **Verify** - Take another screenshot to confirm action succeeded

## Configuration

MCP Server URL: `http://<bytebot-host>:9990/mcp`

Add to Claude Code:
```bash
claude mcp add --transport sse bytebot http://192.168.1.100:9990/mcp
```

Or manually in `~/.mcp.json`:
```json
{
  "mcpServers": {
    "bytebot": {
      "url": "http://192.168.1.100:9990/mcp",
      "transport": "sse"
    }
  }
}
```

## Services

| Service | URL | Purpose |
|---------|-----|---------|
| MCP SSE | `:9990/mcp` | MCP tool server |
| REST API | `:9990/computer-use` | Direct API access |
| VNC | `:9990/vnc` | Browser-based desktop view |

## Notes

- No API key required for desktop control (self-hosted)
- AI provider key (Anthropic/OpenAI/Gemini) only needed for bytebot-agent natural language processing
- Desktop runs in isolated Docker container
- Screenshots may be large - compression applied automatically
