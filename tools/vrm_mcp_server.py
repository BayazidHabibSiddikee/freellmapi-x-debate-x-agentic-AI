"""
VRM Control MCP Server
Exposes VRM avatar control as MCP tools for use with opencode, claude, kiro, gemini.
"""
import socket
import json
import sys
from pythonosc import osc_message_builder

VMC_IP = "127.0.0.1"
VMC_PORT = 39539

BLEND_SHAPES = {
    "happy": "Joy", "angry": "Angry", "sad": "Sorrow",
    "relaxed": "Relief", "surprised": "Surprise", "neutral": "Neutral",
    "blink": "Blink", "blink_left": "BlinkLeft", "blink_right": "BlinkRight",
    "aa": "Aa", "ih": "Ih", "ou": "Ou", "ee": "Ee", "oh": "Oh",
    "look_up": "LookUp", "look_down": "LookDown",
    "look_left": "LookLeft", "look_right": "LookRight",
}

EXPRESSION_PRESETS = {
    "happy":     {"Joy": 0.8, "Angry": 0.0, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 0.3},
    "angry":     {"Joy": 0.0, "Angry": 0.9, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 0.1},
    "sad":       {"Joy": 0.0, "Angry": 0.0, "Sorrow": 0.8, "Surprise": 0.0, "Blink": 0.5},
    "surprised": {"Joy": 0.0, "Angry": 0.0, "Sorrow": 0.0, "Surprise": 0.9, "Blink": 0.0},
    "neutral":   {"Joy": 0.1, "Angry": 0.0, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 0.2},
    "wink":      {"Joy": 0.3, "Angry": 0.0, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 1.0, "BlinkLeft": 1.0},
    "thinking":  {"Joy": 0.0, "Angry": 0.1, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 0.4, "LookUp": 0.6},
    "laughing":  {"Joy": 1.0, "Angry": 0.0, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 0.0, "Aa": 0.7},
}


def send_osc(address, args):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    msg = osc_message_builder.OscMessageBuilder(address=address)
    for arg in args:
        msg.add_arg(arg)
    packet = msg.build()
    sock.sendto(packet.dgram, (VMC_IP, VMC_PORT))
    sock.close()


def handle_request(req):
    method = req.get("method", "")
    params = req.get("params", {})
    req_id = req.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "vrm-control", "version": "1.0.0"}
        }}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": [
            {
                "name": "vrm_set_expression",
                "description": "Set a preset expression on the VRM avatar (happy, angry, sad, surprised, neutral, wink, thinking, laughing)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "enum": list(EXPRESSION_PRESETS.keys()), "description": "Expression to apply"},
                        "intensity": {"type": "number", "description": "Override intensity 0.0-1.0 for all shapes"}
                    },
                    "required": ["expression"]
                }
            },
            {
                "name": "vrm_set_blendshape",
                "description": "Set a single VRM blendshape (Joy, Angry, Sorrow, Surprise, Blink, BlinkLeft, BlinkRight, Aa, Ih, Ou, Ee, Oh, LookUp, LookDown, LookLeft, LookRight)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "shape": {"type": "string", "description": "Blendshape name"},
                        "intensity": {"type": "number", "description": "Value 0.0 to 1.0", "default": 1.0}
                    },
                    "required": ["shape"]
                }
            },
            {
                "name": "vrm_set_multiple_blendshapes",
                "description": "Set multiple VRM blendshapes at once",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "shapes": {"type": "object", "description": "Dict of shape name -> intensity 0.0-1.0", "example": {"Joy": 0.8, "Blink": 0.3}}
                    },
                    "required": ["shapes"]
                }
            },
            {
                "name": "vrm_reset",
                "description": "Reset VRM avatar to neutral pose",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "vrm_list_expressions",
                "description": "List all available VRM expressions and blendshapes",
                "inputSchema": {"type": "object", "properties": {}}
            }
        ]}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        if tool_name == "vrm_set_expression":
            expr = args.get("expression", "neutral")
            intensity = args.get("intensity")
            preset = EXPRESSION_PRESETS.get(expr, EXPRESSION_PRESETS["neutral"])
            if intensity is not None:
                preset = {k: float(intensity) for k in preset}
            send_osc("/vmc/blend/val", [])
            for shape, val in preset.items():
                send_osc("/vmc/blend/val", [shape, float(val)])
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": f"Expression set to: {expr}"}]}}

        if tool_name == "vrm_set_blendshape":
            shape = args.get("shape", "Joy")
            intensity = float(args.get("intensity", 1.0))
            send_osc("/vmc/blend/val", [shape, max(0.0, min(1.0, intensity))])
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": f"Blendshape {shape} = {intensity}"}]}}

        if tool_name == "vrm_set_multiple_blendshapes":
            shapes = args.get("shapes", {})
            for shape, val in shapes.items():
                send_osc("/vmc/blend/val", [shape, max(0.0, min(1.0, float(val)))])
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": f"Set {len(shapes)} blendshapes: {shapes}"}]}}

        if tool_name == "vrm_reset":
            reset = {v: 0.0 for v in BLEND_SHAPES.values()}
            reset["Neutral"] = 1.0
            reset["Blink"] = 0.2
            for shape, val in reset.items():
                send_osc("/vmc/blend/val", [shape, float(val)])
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": "Avatar reset to neutral"}]}}

        if tool_name == "vrm_list_expressions":
            info = json.dumps({"expressions": list(EXPRESSION_PRESETS.keys()), "blendshapes": list(BLEND_SHAPES.values())}, indent=2)
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": info}]}}

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


if __name__ == "__main__":
    # Stdio MCP transport - read JSON-RPC from stdin, write to stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            print(json.dumps(resp), flush=True)
        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}), flush=True)
