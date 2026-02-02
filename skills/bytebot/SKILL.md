---
name: bytebot
description: Control a containerized Linux desktop via Bytebot API - screenshots, mouse, keyboard, file operations.
homepage: https://github.com/bytebot-ai/bytebot
metadata: {"claude":{"emoji":"🤖","requires":{"mcp":["bytebot","linux-desktop"]}}}
---

# Desktop Automation (Muletto)

## Priority: Linux Desktop MCP (primary) > Bytebot (fallback)

### Linux Desktop MCP (PRIMARY - low token cost)
Uses native AT-SPI2 accessibility APIs. 80-95% less tokens than screenshots.

**Tools:** `desktop_snapshot`, `desktop_find`, `desktop_click`, `desktop_type`, `desktop_key`, `desktop_capabilities`, `desktop_context`, `desktop_target_window`, `desktop_create_window_group`, `desktop_release_window`

**Usage pattern:**
```
# Find element by role/name (semantic, low tokens)
desktop_find {role: "button", name: "Save"}

# Click by reference
desktop_click {ref: "ref_1"}

# Type text
desktop_type {text: "Hello world"}

# Get full accessibility snapshot
desktop_snapshot
```

**When to use:** GTK, Qt, Electron apps - anything with accessibility support.

### Bytebot (FALLBACK - high token cost)
Screenshot-based automation. Use only when Linux Desktop MCP can't find the element.

**Tools:** See original list below.

**When to use:** Legacy apps without AT-SPI, pixel-precise operations, VNC viewing.

## Bytebot Available MCP Tools

### Vision
- `computer_screenshot` - Capture current screen (returns base64 PNG)
- `computer_cursor_position` - Get current mouse coordinates

### Mouse Control
- `computer_move_mouse` - Move cursor to coordinates `{x, y}`
- `computer_click_mouse` - Click at position `{coordinates?, button, clickCount, holdKeys?}`
- `computer_press_mouse` - Press/release mouse button
- `computer_drag_mouse` - Drag along path
- `computer_trace_mouse` - Move along path
- `computer_scroll` - Scroll wheel

### Keyboard Control
- `computer_type_text` - Type text string (< 25 chars)
- `computer_paste_text` - Paste text via clipboard
- `computer_type_keys` - Type key sequence
- `computer_press_keys` - Hold/release keys

### Applications
- `computer_application` - Open/switch app: `firefox`, `vscode`, `terminal`, `desktop`

### File Operations
- `computer_read_file` - Read file from desktop
- `computer_write_file` - Write file to desktop

## Workflow Pattern

1. **Try Linux Desktop MCP first** - `desktop_find` to locate elements
2. **If not found** - Fall back to Bytebot `computer_screenshot` + click
3. **Verify** - Use `desktop_snapshot` or `computer_screenshot` to confirm

## Configuration

Linux Desktop MCP runs inside the Bytebot container via SSH/docker exec.
Bytebot MCP SSE at: `http://192.168.1.100:9990/mcp`
