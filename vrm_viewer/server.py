"""
VRM Viewer Server
Serves the 3D VRM viewer and bridges WebSocket control for real-time emotions.
"""
import asyncio
import json
import os
import socket
import webbrowser
import threading
from pathlib import Path
from aiohttp import web
from websockets import serve

from pythonosc import osc_message_builder

VMC_IP = "127.0.0.1"
VMC_PORT = 39539
HTTP_PORT = 8766
WS_PORT = 8767

VRM_FILE = "/home/sword/Documents/tools/61121190575213457.vrm"

EXPRESSIONS = {
    "happy":     {"Joy": 0.8, "Angry": 0.0, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 0.3},
    "angry":     {"Joy": 0.0, "Angry": 0.9, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 0.1},
    "sad":       {"Joy": 0.0, "Angry": 0.0, "Sorrow": 0.8, "Surprise": 0.0, "Blink": 0.5},
    "surprised": {"Joy": 0.0, "Angry": 0.0, "Sorrow": 0.0, "Surprise": 0.9, "Blink": 0.0},
    "neutral":   {"Joy": 0.1, "Angry": 0.0, "Sorrow": 0.0, "Surprise": 0.0, "Blink": 0.2},
    "wink":      {"Joy": 0.3, "Blink": 1.0, "BlinkLeft": 1.0, "BlinkRight": 0.0},
    "thinking":  {"Joy": 0.0, "Angry": 0.1, "Blink": 0.4, "LookUp": 0.6},
    "laughing":  {"Joy": 1.0, "Blink": 0.0, "Aa": 0.7, "Ih": 0.2},
}

connected_clients = set()

HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>VRM Avatar Viewer</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #1a1a2e; font-family: 'Segoe UI', sans-serif; overflow: hidden; }
#canvas-container { width: 100vw; height: 100vh; }
canvas { display: block; }
#controls {
    position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
    background: rgba(0,0,0,0.85); border-radius: 16px; padding: 16px 24px;
    display: flex; gap: 10px; flex-wrap: wrap; justify-content: center;
    z-index: 10; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1);
}
#controls button {
    padding: 10px 20px; border: none; border-radius: 10px; cursor: pointer;
    font-size: 14px; font-weight: 600; transition: all 0.2s; color: white;
}
#controls button:hover { transform: scale(1.05); filter: brightness(1.2); }
#controls button.active { box-shadow: 0 0 15px rgba(255,255,255,0.4); }
.btn-happy { background: linear-gradient(135deg, #f093fb, #f5576c); }
.btn-angry { background: linear-gradient(135deg, #ff416c, #ff4b2b); }
.btn-sad { background: linear-gradient(135deg, #4facfe, #00f2fe); }
.btn-surprised { background: linear-gradient(135deg, #ffd200, #f7971e); }
.btn-neutral { background: linear-gradient(135deg, #868f96, #596164); }
.btn-wink { background: linear-gradient(135deg, #a18cd1, #fbc2eb); }
.btn-thinking { background: linear-gradient(135deg, #667eea, #764ba2); }
.btn-laughing { background: linear-gradient(135deg, #43e97b, #38f9d7); color: #333; }
#status {
    position: fixed; top: 20px; left: 20px; color: #0f0; font-size: 13px;
    font-family: monospace; z-index: 10; background: rgba(0,0,0,0.7);
    padding: 8px 12px; border-radius: 8px;
}
#current-emotion {
    position: fixed; top: 20px; right: 20px; color: white; font-size: 18px;
    font-weight: bold; z-index: 10; background: rgba(0,0,0,0.7);
    padding: 10px 18px; border-radius: 10px; text-transform: capitalize;
}
#slider-container {
    position: fixed; right: 20px; top: 50%; transform: translateY(-50%);
    background: rgba(0,0,0,0.8); padding: 16px; border-radius: 12px;
    z-index: 10; display: flex; flex-direction: column; gap: 8px; min-width: 200px;
}
#slider-container label { color: #aaa; font-size: 12px; }
#slider-container input[type=range] { width: 100%; }
#slider-container .val { color: #0f0; font-family: monospace; font-size: 11px; }
</style>
</head>
<body>
<div id="canvas-container"></div>
<div id="status">WS: connecting...</div>
<div id="current-emotion">neutral</div>

<div id="slider-container">
    <label>Blink</label>
    <input type="range" id="sl-blink" min="0" max="100" value="20"
           oninput="sendSlider('Blink', this.value)">
    <div class="val" id="v-blink">0.2</div>
    <label>Look X</label>
    <input type="range" id="sl-lookx" min="-100" max="100" value="0"
           oninput="sendSlider('LookX', this.value)">
    <div class="val" id="v-lookx">0.0</div>
    <label>Look Y</label>
    <input type="range" id="sl-looky" min="-100" max="100" value="0"
           oninput="sendSlider('LookY', this.value)">
    <div class="val" id="v-looky">0.0</div>
</div>

<div id="controls">
    <button class="btn-happy" onclick="setExpression('happy')">Happy</button>
    <button class="btn-angry" onclick="setExpression('angry')">Angry</button>
    <button class="btn-sad" onclick="setExpression('sad')">Sad</button>
    <button class="btn-surprised" onclick="setExpression('surprised')">Surprised</button>
    <button class="btn-neutral" onclick="setExpression('neutral')">Neutral</button>
    <button class="btn-wink" onclick="setExpression('wink')">Wink</button>
    <button class="btn-thinking" onclick="setExpression('thinking')">Thinking</button>
    <button class="btn-laughing" onclick="setExpression('laughing')">Laughing</button>
</div>

<script type="importmap">
{
    "imports": {
        "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
        "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/",
        "@pixiv/three-vrm": "https://cdn.jsdelivr.net/npm/@pixiv/three-vrm@3.3.3/lib/three-vrm.module.min.js"
    }
}
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';

const VRM_URL = '/model.vrm';
let vrm = null;
let ws = null;

// Three.js setup
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a2e);

const camera = new THREE.PerspectiveCamera(28, window.innerWidth / window.innerHeight, 0.01, 500);
camera.position.set(0, 1.0, 3.5);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.2;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = false;
document.getElementById('canvas-container').appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0.9, 0);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 0.5;
controls.maxDistance = 15;
controls.maxPolarAngle = Math.PI * 0.9;

// Lights — bright and soft for full visibility
const dirLight = new THREE.DirectionalLight(0xffffff, 2.0);
dirLight.position.set(2, 3, 4);
scene.add(dirLight);

const fillLight = new THREE.DirectionalLight(0xffffff, 1.2);
fillLight.position.set(-3, 2, -2);
scene.add(fillLight);

const topLight = new THREE.DirectionalLight(0xffffff, 0.8);
topLight.position.set(0, 5, 0);
scene.add(topLight);

scene.add(new THREE.AmbientLight(0xffffff, 0.8));

// Grid
const grid = new THREE.GridHelper(6, 30, 0x555577, 0x444466);
scene.add(grid);

// Load VRM
function loadVRM() {
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(VRM_URL, (gltf) => {
        vrm = gltf.userData.vrm;
        scene.add(vrm.scene);
        vrm.scene.rotation.y = Math.PI;

        // DON'T touch materials — let VRMLoaderPlugin + GLTFLoader handle them natively
        // Only fix color space on textures and ensure meshes render
        vrm.scene.traverse((child) => {
            if (!child.isMesh) return;
            child.frustumCulled = false;

            // Fix texture color space only — leave materials alone
            const fixTex = (tex) => {
                if (tex && tex.colorSpace !== undefined) {
                    tex.colorSpace = THREE.SRGBColorSpace;
                    tex.needsUpdate = true;
                }
            };

            const mats = Array.isArray(child.material) ? child.material : [child.material];
            mats.forEach(m => {
                if (m.map) fixTex(m.map);
                if (m.normalMap) fixTex(m.normalMap);
                if (m.emissiveMap) fixTex(m.emissiveMap);
            });
        });

        // Auto-frame the model
        const box = new THREE.Box3().setFromObject(vrm.scene);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const fov = camera.fov * (Math.PI / 180);
        const dist = maxDim / (2 * Math.tan(fov / 2)) * 1.2;

        controls.target.copy(center);
        camera.position.set(center.x, center.y + size.y * 0.05, center.z + dist);
        camera.lookAt(center);
        controls.update();

        document.getElementById('status').textContent = 'WS: connected | VRM loaded';
        document.getElementById('status').style.color = '#0f0';
    }, (progress) => {
        if (progress.total) {
            const pct = Math.round((progress.loaded / progress.total) * 100);
            document.getElementById('status').textContent = 'Loading... ' + pct + '%';
        }
    }, (err) => {
        document.getElementById('status').textContent = 'Error: ' + err.message;
        document.getElementById('status').style.color = '#f00';
    });
}

loadVRM();

// Expression presets
const EXPRESSIONS = {
    happy:     { Joy: 0.8, Angry: 0.0, Sorrow: 0.0, Surprise: 0.0, Blink: 0.3 },
    angry:     { Joy: 0.0, Angry: 0.9, Sorrow: 0.0, Surprise: 0.0, Blink: 0.1 },
    sad:       { Joy: 0.0, Angry: 0.0, Sorrow: 0.8, Surprise: 0.0, Blink: 0.5 },
    surprised: { Joy: 0.0, Angry: 0.0, Sorrow: 0.0, Surprise: 0.9, Blink: 0.0 },
    neutral:   { Joy: 0.1, Angry: 0.0, Sorrow: 0.0, Surprise: 0.0, Blink: 0.2 },
    wink:      { Joy: 0.3, Blink: 1.0, BlinkLeft: 1.0, BlinkRight: 0.0 },
    thinking:  { Joy: 0.0, Angry: 0.1, Blink: 0.4, LookUp: 0.6 },
    laughing:  { Joy: 1.0, Blink: 0.0, Aa: 0.7, Ih: 0.2 },
};

window.setExpression = function(name) {
    const shapes = EXPRESSIONS[name] || EXPRESSIONS.neutral;
    if (vrm && vrm.expressionManager) {
        for (const [key, val] of Object.entries(shapes)) {
            vrm.expressionManager.setValue(key, val);
        }
    }
    document.getElementById('current-emotion').textContent = name;
    document.querySelectorAll('#controls button').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'expression', name, shapes }));
};

window.sendSlider = function(name, val) {
    const v = val / 100;
    document.getElementById('v-' + name.toLowerCase().replace('look','look')).textContent = v.toFixed(2);
    if (vrm && vrm.expressionManager) {
        if (name === 'Blink') vrm.expressionManager.setValue('Blink', v);
        if (name === 'LookX') vrm.expressionManager.setValue('LookLeft', v < 0 ? -v : 0);
        if (name === 'LookX') vrm.expressionManager.setValue('LookRight', v > 0 ? v : 0);
        if (name === 'LookY') vrm.expressionManager.setValue('LookUp', v > 0 ? v : 0);
        if (name === 'LookY') vrm.expressionManager.setValue('LookDown', v < 0 ? -v : 0);
    }
};

// WebSocket
function connectWS() {
    ws = new WebSocket('ws://' + location.hostname + ':8767');
    ws.onopen = () => { document.getElementById('status').textContent = 'WS: connected | VRM loaded'; };
    ws.onclose = () => { document.getElementById('status').textContent = 'WS: disconnected, retrying...'; setTimeout(connectWS, 2000); };
    ws.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data.type === 'expression' && data.name) {
                window.setExpression(data.name);
            } else if (data.type === 'blendshape' && data.shape) {
                if (vrm && vrm.expressionManager) {
                    vrm.expressionManager.setValue(data.shape, data.intensity || 0);
                }
            } else if (data.type === 'shapes' && data.shapes) {
                if (vrm && vrm.expressionManager) {
                    for (const [k, v] of Object.entries(data.shapes)) {
                        vrm.expressionManager.setValue(k, v);
                    }
                }
            }
        } catch {}
    };
}
connectWS();

// Animate
function animate() {
    requestAnimationFrame(animate);
    controls.update();
    if (vrm) vrm.update();
    renderer.render(scene, camera);
}
animate();

window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});
</script>
</body>
</html>"""


# --- WebSocket server for real-time control ---
async def ws_handler(websocket):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            pass  # We only send TO the viewer
    finally:
        connected_clients.discard(websocket)


def broadcast(data):
    """Send expression data to all connected browser viewers."""
    msg = json.dumps(data)
    for client in list(connected_clients):
        try:
            asyncio.get_event_loop().create_task(client.send(msg))
        except Exception:
            connected_clients.discard(client)


def send_vmc(shapes):
    """Send VMC packets to external receivers (VPuppr etc)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for name, val in shapes.items():
        msg = osc_message_builder.OscMessageBuilder(address="/vmc/blend/val")
        msg.add_arg(name)
        msg.add_arg(float(val))
        packet = msg.build()
        sock.sendto(packet.dgram, (VMC_IP, VMC_PORT))
    sock.close()


# --- HTTP routes ---
async def index(request):
    return web.Response(text=HTML_PAGE, content_type='text/html')

async def model(request):
    return web.FileResponse(VRM_FILE)

async def api_expression(request):
    data = await request.json()
    name = data.get("expression", "neutral")
    intensity = data.get("intensity")
    shapes = EXPRESSIONS.get(name, EXPRESSIONS["neutral"])
    if intensity is not None:
        shapes = {k: float(intensity) for k in shapes}

    broadcast({"type": "expression", "name": name, "shapes": shapes})
    send_vmc(shapes)
    return web.json_response({"status": "ok", "expression": name, "shapes": shapes})

async def api_blendshape(request):
    data = await request.json()
    shape = data.get("shape", "Joy")
    intensity = float(data.get("intensity", 1.0))
    broadcast({"type": "blendshape", "shape": shape, "intensity": intensity})
    send_vmc({shape: intensity})
    return web.json_response({"status": "ok", "shape": shape, "intensity": intensity})

async def api_expressions_list(request):
    return web.json_response({"expressions": list(EXPRESSIONS.keys())})

async def api_health(request):
    return web.json_response({"status": "ok", "viewers": len(connected_clients)})


async def start_ws_server():
    server = await serve(ws_handler, "0.0.0.0", WS_PORT)
    await server.wait_closed()


def run_ws():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_ws_server())


async def main():
    app = web.Application()
    app.router.add_get('/', index)
    app.router.add_get('/model.vrm', model)
    app.router.add_post('/api/expression', api_expression)
    app.router.add_post('/api/blendshape', api_blendshape)
    app.router.add_get('/api/expressions', api_expressions_list)
    app.router.add_get('/api/health', api_health)

    # Start WebSocket server in background thread
    ws_thread = threading.Thread(target=run_ws, daemon=True)
    ws_thread.start()

    # Open browser
    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{HTTP_PORT}")).start()

    print(f"\n{'='*50}")
    print(f"  VRM Viewer running at http://localhost:{HTTP_PORT}")
    print(f"  WebSocket control on ws://localhost:{WS_PORT}")
    print(f"  VRM file: {VRM_FILE}")
    print(f"{'='*50}\n")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
    await site.start()

    # Keep running
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
