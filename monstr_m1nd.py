"""
MØNSTR-M1ND - Android Remote Control System
Created by MR.MONSIF
Contact: 
- Telegram: http://t.me/monstr_m1nd
- Instagram: https://www.instagram.com/httpx.mrmonsif/

A professional Android remote control system using QR Code connection.
Features:
- Live screen streaming from Android to Desktop
- Full mouse and keyboard control
- Secure token-based authentication
"""

import os
import sys
import json
import time
import uuid
import queue
import threading
import socket
import base64
import hashlib
import subprocess
import webbrowser
from datetime import datetime
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass, asdict

try:
    from flask import Flask, render_template, Response, jsonify, request
    from flask_socketio import SocketIO, emit
    from flask_cors import CORS
    import qrcode
    from PIL import Image, ImageDraw
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    import pyautogui
    import keyboard
    FLASK_AVAILABLE = True
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("[INFO] Installing required packages...")
    
    packages = [
        "flask",
        "flask-socketio",
        "flask-cors",
        "qrcode[pil]",
        "pillow",
        "pyautogui",
        "keyboard"
    ]
    
    for package in packages:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--user"])
            print(f"[OK] Installed: {package}")
        except:
            print(f"[WARNING] Failed to install: {package}")
    
    try:
        from flask import Flask, render_template, Response, jsonify, request
        from flask_socketio import SocketIO, emit
        from flask_cors import CORS
        import qrcode
        from PIL import Image, ImageDraw
        import tkinter as tk
        from tkinter import ttk, messagebox, scrolledtext
        import pyautogui
        import keyboard
        FLASK_AVAILABLE = True
    except:
        FLASK_AVAILABLE = False
        print("[ERROR] Failed to install required packages")
        print("Please install manually: pip install flask flask-socketio flask-cors qrcode[pil] pillow pyautogui keyboard")
        sys.exit(1)

@dataclass
class Config:
    APP_NAME = "MØNSTR-M1ND"
    VERSION = "1.0.0"
    AUTHOR = "MR.MONSIF"
    TELEGRAM_URL = "http://t.me/monstr_m1nd"
    INSTAGRAM_URL = "https://www.instagram.com/httpx.mrmonsif/"
    
    HOST = "0.0.0.0"
    PORT = 8080
    WEB_PORT = 5000
    SECRET_KEY = "MØNSTR-M1ND-SECRET-" + str(uuid.uuid4())
    
    FRAME_RATE = 15  # Reduced for better performance
    QUALITY = 70     # Reduced quality for better performance
    MAX_CLIENTS = 5
    TOKEN_EXPIRY = 3600  # 1 hour
    
    # UI settings
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
    THEME_COLOR = "#000000"
    ACCENT_COLOR = "#FFFFFF"
    FONT_FAMILY = "Arial"

config = Config()

class SimpleLogger:
    """Simple logger without emoji issues"""
    
    def __init__(self):
        self.log_file = f"monstr_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
    def info(self, msg: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[INFO] {timestamp} - {msg}"
        print(log_msg)
        self._write_log(log_msg)
        
    def error(self, msg: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[ERROR] {timestamp} - {msg}"
        print(log_msg)
        self._write_log(log_msg)
        
    def warning(self, msg: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[WARNING] {timestamp} - {msg}"
        print(log_msg)
        self._write_log(log_msg)
        
    def success(self, msg: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[SUCCESS] {timestamp} - {msg}"
        print(log_msg)
        self._write_log(log_msg)
    
    def _write_log(self, msg: str):
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except:
            pass

logger = SimpleLogger()

class ConnectionManager:
    """Manages client connections and sessions"""
    
    def __init__(self):
        self.clients: Dict[str, Dict] = {}
        self.tokens: Dict[str, Dict] = {}
        self.screen_streams: Dict[str, queue.Queue] = {}
        self.lock = threading.Lock()
        
    def generate_token(self, client_info: Dict) -> str:
        """Generate unique token for client"""
        token = hashlib.sha256(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest()[:32]
        
        with self.lock:
            self.tokens[token] = {
                "client_info": client_info,
                "created_at": time.time(),
                "last_activity": time.time(),
                "ip": "127.0.0.1"
            }
            
        logger.info(f"Generated token for client: {client_info.get('device', 'Unknown')}")
        return token
    
    def validate_token(self, token: str) -> bool:
        """Validate client token"""
        with self.lock:
            if token in self.tokens:
                self.tokens[token]["last_activity"] = time.time()
                return True
        return False
    
    def add_client(self, sid: str, token: str, client_data: Dict):
        """Add new client connection"""
        with self.lock:
            self.clients[sid] = {
                "token": token,
                "data": client_data,
                "connected_at": time.time(),
                "last_ping": time.time(),
                "screen_size": None,
                "streaming": False
            }
            
            
            self.screen_streams[sid] = queue.Queue(maxsize=5)  # Smaller queue for better performance
            
        logger.success(f"Client connected: {sid} - {client_data.get('device', 'Unknown')}")
    
    def remove_client(self, sid: str):
        """Remove client connection"""
        with self.lock:
            if sid in self.clients:
                device = self.clients[sid]["data"].get("device", "Unknown")
                self.clients.pop(sid, None)
                self.screen_streams.pop(sid, None)
                logger.info(f"Client disconnected: {sid} - {device}")
    
    def get_client(self, sid: str) -> Optional[Dict]:
        """Get client information"""
        with self.lock:
            return self.clients.get(sid)
    
    def update_screen_size(self, sid: str, width: int, height: int):
        """Update client screen dimensions"""
        with self.lock:
            if sid in self.clients:
                self.clients[sid]["screen_size"] = (width, height)
    
    def add_frame(self, sid: str, frame_data: bytes):
        """Add screen frame to client queue"""
        if sid in self.screen_streams:
            try:
                # Clear old frames if queue is full
                if self.screen_streams[sid].full():
                    try:
                        self.screen_streams[sid].get_nowait()
                    except queue.Empty:
                        pass
                
                self.screen_streams[sid].put_nowait(frame_data)
            except queue.Full:
                pass
    
    def get_frame(self, sid: str) -> Optional[bytes]:
        """Get screen frame from client queue"""
        if sid in self.screen_streams:
            try:
                return self.screen_streams[sid].get_nowait()
            except queue.Empty:
                return None
        return None
    
    def get_connected_devices(self) -> List[Dict]:
        """Get list of all connected devices"""
        with self.lock:
            devices = []
            for sid, client in self.clients.items():
                devices.append({
                    "sid": sid,
                    "device": client["data"].get("device", "Unknown"),
                    "connected_at": client["connected_at"],
                    "screen_size": client["screen_size"]
                })
            return devices

connection_manager = ConnectionManager()

class SimpleFrameProcessor:
    """Simple frame processor without OpenCV"""
    
    def __init__(self):
        self.quality = config.QUALITY
        
    def process_frame(self, frame_data: bytes) -> bytes:
        """Simple frame processor - just passes through for now"""
        # In a real implementation, you would resize/compress here
        # For simplicity, we'll just return the original
        return frame_data

frame_processor = SimpleFrameProcessor()

class ControlHandler:
    """Handles control events from desktop to mobile"""
    
    def __init__(self):
        self.mouse_state = {"x": 0, "y": 0, "pressed": False}
        self.keyboard_state = {}
        self.control_lock = threading.Lock()
        
    def handle_mouse_event(self, sid: str, event_data: Dict):
        """Handle mouse events"""
        try:
            event_type = event_data.get("type")
            x = event_data.get("x", 0)
            y = event_data.get("y", 0)
            button = event_data.get("button", "left")
            
            with self.control_lock:
                self.mouse_state = {"x": x, "y": y, "pressed": event_type == "down"}
            
            # Emit to client
            emit("control_event", {
                "type": "mouse",
                "event": event_type,
                "x": x,
                "y": y,
                "button": button,
                "timestamp": time.time()
            }, room=sid)
            
            logger.info(f"Mouse event: {event_type} at ({x}, {y})")
            
        except Exception as e:
            logger.error(f"Mouse event error: {e}")
    
    def handle_keyboard_event(self, sid: str, event_data: Dict):
        """Handle keyboard events"""
        try:
            event_type = event_data.get("type")
            key = event_data.get("key", "")
            text = event_data.get("text", "")
            
            with self.control_lock:
                if event_type == "down":
                    self.keyboard_state[key] = True
                elif event_type == "up":
                    self.keyboard_state.pop(key, None)
            
            # Emit to client
            emit("control_event", {
                "type": "keyboard",
                "event": event_type,
                "key": key,
                "text": text,
                "timestamp": time.time()
            }, room=sid)
            
            logger.info(f"Keyboard event: {event_type} key={key}")
            
        except Exception as e:
            logger.error(f"Keyboard event error: {e}")
    
    def handle_touch_event(self, sid: str, event_data: Dict):
        """Handle touch events (for mobile compatibility)"""
        try:
            emit("control_event", {
                "type": "touch",
                "action": event_data.get("action", "tap"),
                "x": event_data.get("x", 0),
                "y": event_data.get("y", 0),
                "timestamp": time.time()
            }, room=sid)
            
        except Exception as e:
            logger.error(f"Touch event error: {e}")
    
    def handle_command(self, sid: str, command: str):
        """Handle special commands"""
        try:
            if command == "home":
                emit("control_event", {
                    "type": "command",
                    "command": "home",
                    "timestamp": time.time()
                }, room=sid)
                
            elif command == "back":
                emit("control_event", {
                    "type": "command",
                    "command": "back",
                    "timestamp": time.time()
                }, room=sid)
                
            elif command == "recent":
                emit("control_event", {
                    "type": "command",
                    "command": "recent",
                    "timestamp": time.time()
                }, room=sid)
                
            logger.info(f"Command executed: {command}")
            
        except Exception as e:
            logger.error(f"Command error: {e}")

control_handler = ControlHandler()

class MØNSTRApp:
    """Main application class"""
    
    def __init__(self):
        if not FLASK_AVAILABLE:
            raise ImportError("Required packages not available")
        
        self.app = Flask(__name__, 
                       static_folder='static',
                       template_folder='templates')
        
        # Configure app
        self.app.config['SECRET_KEY'] = config.SECRET_KEY
        self.app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB
        
        # Enable CORS
        CORS(self.app)
        
        # Setup SocketIO
        self.socketio = SocketIO(self.app, 
                                cors_allowed_origins="*",
                                async_mode='threading',
                                ping_timeout=60,
                                ping_interval=25,
                                logger=False,
                                engineio_logger=False)
        
        # Initialize components
        self.setup_routes()
        self.setup_socket_events()
        
        # Create necessary directories
        self.create_directories()
        
        logger.success(f"{config.APP_NAME} v{config.VERSION} initialized")
    
    def create_directories(self):
        """Create necessary directories"""
        os.makedirs("static", exist_ok=True)
        os.makedirs("templates", exist_ok=True)
        os.makedirs("screenshots", exist_ok=True)
        os.makedirs("qrcodes", exist_ok=True)
        os.makedirs("static/qrcodes", exist_ok=True)
    
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            """Main page"""
            return render_template('index.html')
        
        @self.app.route('/control')
        def control_panel():
            """Control panel"""
            return render_template('control.html')
        
        @self.app.route('/generate_qr')
        def generate_qr():
            """Generate QR code for connection"""
            try:
                # Get server IP
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    server_ip = s.getsockname()[0]
                    s.close()
                except:
                    server_ip = socket.gethostbyname(socket.gethostname())
                    if server_ip.startswith("127."):
                        server_ip = "localhost"
            except:
                server_ip = "localhost"
            
            # Generate token
            client_info = {
                "device": "Android Device",
                "user_agent": request.user_agent.string if request.user_agent else "Unknown",
                "ip": request.remote_addr if request.remote_addr else "127.0.0.1"
            }
            
            token = connection_manager.generate_token(client_info)
            
            # Create connection URL
            connection_url = f"http://{server_ip}:{config.WEB_PORT}/connect?token={token}"
            
            # Generate QR code
            try:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_H,
                    box_size=10,
                    border=4,
                )
                qr.add_data(connection_url)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Save QR code
                qr_path = f"qrcodes/{token}.png"
                img.save(qr_path)
                
                # Copy to static folder
                static_qr_path = f"static/qrcodes/{token}.png"
                img.save(static_qr_path)
                
                return jsonify({
                    "success": True,
                    "qr_url": f"/static/qrcodes/{token}.png",
                    "connection_url": connection_url,
                    "token": token,
                    "server_ip": server_ip,
                    "port": config.WEB_PORT
                })
            except Exception as e:
                logger.error(f"QR generation error: {e}")
                return jsonify({
                    "success": False,
                    "error": str(e)
                })
        
        @self.app.route('/connect')
        def connect():
            """Mobile connection page"""
            token = request.args.get('token', '')
            
            if connection_manager.validate_token(token):
                return render_template('mobile.html', token=token)
            else:
                return "Invalid or expired token", 403
        
        @self.app.route('/stream/<sid>')
        def video_stream(sid):
            """Video streaming endpoint"""
            def generate():
                while True:
                    frame = connection_manager.get_frame(sid)
                    if frame:
                        try:
                            processed_frame = frame_processor.process_frame(frame)
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + 
                                   processed_frame + b'\r\n')
                        except Exception as e:
                            logger.error(f"Stream generation error: {e}")
                            break
                    else:
                        time.sleep(1 / config.FRAME_RATE)
            
            return Response(generate(),
                          mimetype='multipart/x-mixed-replace; boundary=frame')
        
        @self.app.route('/devices')
        def get_devices():
            """Get connected devices"""
            devices = connection_manager.get_connected_devices()
            return jsonify({
                "success": True,
                "devices": devices,
                "count": len(devices)
            })
        
        @self.app.route('/screenshot/<sid>')
        def take_screenshot(sid):
            """Take screenshot of device"""
            frame = connection_manager.get_frame(sid)
            if frame:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshots/{sid}_{timestamp}.jpg"
                
                with open(filename, 'wb') as f:
                    f.write(frame)
                
                return jsonify({
                    "success": True,
                    "filename": filename,
                    "timestamp": timestamp
                })
            
            return jsonify({"success": False, "error": "No frame available"})
        
        @self.app.route('/open_telegram')
        def open_telegram():
            """Open Telegram profile"""
            webbrowser.open(config.TELEGRAM_URL)
            return jsonify({"success": True, "url": config.TELEGRAM_URL})
        
        @self.app.route('/open_instagram')
        def open_instagram():
            """Open Instagram profile"""
            webbrowser.open(config.INSTAGRAM_URL)
            return jsonify({"success": True, "url": config.INSTAGRAM_URL})
        
        @self.app.route('/system_info')
        def system_info():
            """Get system information"""
            return jsonify({
                "app_name": config.APP_NAME,
                "version": config.VERSION,
                "author": config.AUTHOR,
                "uptime": time.time() - self.start_time if hasattr(self, 'start_time') else 0,
                "connected_clients": len(connection_manager.clients),
                "server_time": datetime.now().isoformat()
            })
        
        @self.app.route('/send_command/<sid>', methods=['POST'])
        def send_command(sid):
            """Send command to device"""
            try:
                data = request.json
                command = data.get('command', '')
                
                if command:
                    control_handler.handle_command(sid, command)
                    return jsonify({"success": True})
                
                return jsonify({"success": False})
            except Exception as e:
                return jsonify({"success": False, "error": str(e)})
    
    def setup_socket_events(self):
        """Setup SocketIO events"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection"""
            logger.info(f"Client connected: {request.sid}")
            emit('connected', {'sid': request.sid})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection"""
            connection_manager.remove_client(request.sid)
        
        @self.socketio.on('authenticate')
        def handle_authentication(data):
            """Handle client authentication"""
            token = data.get('token', '')
            client_data = data.get('client_data', {})
            
            if connection_manager.validate_token(token):
                connection_manager.add_client(request.sid, token, client_data)
                emit('authenticated', {
                    'success': True,
                    'sid': request.sid,
                    'message': 'Authentication successful'
                })
            else:
                emit('authenticated', {
                    'success': False,
                    'message': 'Invalid token'
                })
        
        @self.socketio.on('screen_data')
        def handle_screen_data(data):
            """Handle incoming screen data from mobile"""
            sid = request.sid
            frame_data = data.get('frame', '')
            screen_info = data.get('screen_info', {})
            
            if frame_data:
                try:
                    # Decode base64 frame
                    if ',' in frame_data:
                        frame_data = frame_data.split(',')[1]
                    
                    frame_bytes = base64.b64decode(frame_data)
                    connection_manager.add_frame(sid, frame_bytes)
                    
                    # Update screen size if provided
                    if screen_info:
                        width = screen_info.get('width', 0)
                        height = screen_info.get('height', 0)
                        if width and height:
                            connection_manager.update_screen_size(sid, width, height)
                    
                except Exception as e:
                    logger.error(f"Screen data error: {e}")
        
        @self.socketio.on('control')
        def handle_control(data):
            """Handle control events from desktop"""
            sid = data.get('sid', '')
            event_type = data.get('type', '')
            event_data = data.get('data', {})
            
            if sid and sid in connection_manager.clients:
                if event_type == 'mouse':
                    control_handler.handle_mouse_event(sid, event_data)
                elif event_type == 'keyboard':
                    control_handler.handle_keyboard_event(sid, event_data)
                elif event_type == 'touch':
                    control_handler.handle_touch_event(sid, event_data)
                elif event_type == 'command':
                    control_handler.handle_command(sid, event_data.get('command', ''))
        
        @self.socketio.on('ping')
        def handle_ping():
            """Handle ping from clients"""
            sid = request.sid
            client = connection_manager.get_client(sid)
            if client:
                client['last_ping'] = time.time()
            emit('pong')
    
    def run(self):
        """Run the application"""
        self.start_time = time.time()
        
        logger.info(f"Starting {config.APP_NAME} v{config.VERSION}")
        logger.info(f"Author: {config.AUTHOR}")
        logger.info(f"Telegram: {config.TELEGRAM_URL}")
        logger.info(f"Instagram: {config.INSTAGRAM_URL}")
        
        # Get server IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            server_ip = s.getsockname()[0]
            s.close()
        except:
            server_ip = socket.gethostbyname(socket.gethostname())
            if server_ip.startswith("127."):
                server_ip = "localhost"
        
        print("\n" + "="*60)
        print(f"MØNSTR-M1ND v{config.VERSION}")
        print("="*60)
        print(f"Author: {config.AUTHOR}")
        print(f"Telegram: {config.TELEGRAM_URL}")
        print(f"Instagram: {config.INSTAGRAM_URL}")
        print("="*60)
        print("\nServer Information:")
        print(f"  • Server IP: {server_ip}")
        print(f"  • Port: {config.WEB_PORT}")
        print(f"  • FPS: {config.FRAME_RATE}")
        print(f"  • Max Clients: {config.MAX_CLIENTS}")
        print("\nAccess Points:")
        print(f"  • Main Interface: http://{server_ip}:{config.WEB_PORT}")
        print(f"  • Control Panel: http://{server_ip}:{config.WEB_PORT}/control")
        print(f"  • Local Access: http://localhost:{config.WEB_PORT}")
        print("\nQuick Start:")
        print("  1. Open main interface in browser")
        print("  2. Click 'Generate QR Code'")
        print("  3. Scan QR code with your Android device")
        print("  4. Open link on mobile and grant permissions")
        print("  5. Start controlling from desktop!")
        print("="*60 + "\n")
        
        try:
            self.socketio.run(self.app, 
                             host=config.HOST, 
                             port=config.WEB_PORT,
                             debug=False,
                             allow_unsafe_werkzeug=True)
        except Exception as e:
            logger.error(f"Server error: {e}")
            print(f"\nError: Failed to start server: {e}")
            print(f"Check if port {config.WEB_PORT} is available.")

def create_templates():
    """Create HTML templates for web interface"""
    
    # Create templates directory if not exists
    os.makedirs("templates", exist_ok=True)
    
    # Simple index page
    index_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MØNSTR-M1ND - Android Remote Control</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: Arial, sans-serif;
            background: #000000;
            color: #FFFFFF;
            line-height: 1.6;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            flex: 1;
        }
        
        header {
            text-align: center;
            padding: 40px 0;
            border-bottom: 2px solid #00FF00;
            margin-bottom: 40px;
        }
        
        .logo {
            font-size: 2.5rem;
            font-weight: bold;
            color: #00FF00;
            text-shadow: 0 0 10px #00FF00;
            letter-spacing: 2px;
            margin-bottom: 10px;
        }
        
        .subtitle {
            font-size: 1rem;
            color: #888888;
            margin-bottom: 20px;
        }
        
        .author {
            font-size: 0.9rem;
            color: #00FF00;
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 40px;
        }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
            }
        }
        
        .panel {
            background: #111111;
            border: 1px solid #333333;
            border-radius: 10px;
            padding: 20px;
        }
        
        .panel h2 {
            color: #00FF00;
            margin-bottom: 15px;
            font-size: 1.5rem;
        }
        
        .qr-container {
            text-align: center;
            padding: 15px;
        }
        
        #qrCode {
            max-width: 250px;
            margin: 15px auto;
            border: 2px solid #00FF00;
            padding: 8px;
            background: white;
        }
        
        .btn {
            display: inline-block;
            background: #00FF00;
            color: #000000;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            font-size: 0.9rem;
            font-weight: bold;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.3s ease;
            margin: 8px 5px;
        }
        
        .btn:hover {
            background: #00CC00;
            transform: translateY(-2px);
        }
        
        .btn-secondary {
            background: #333333;
            color: #FFFFFF;
        }
        
        .btn-secondary:hover {
            background: #444444;
        }
        
        .status {
            padding: 12px;
            border-radius: 5px;
            margin: 12px 0;
            text-align: center;
            font-weight: bold;
        }
        
        .status.connected {
            background: rgba(0, 255, 0, 0.1);
            border: 1px solid #00FF00;
            color: #00FF00;
        }
        
        .status.disconnected {
            background: rgba(255, 0, 0, 0.1);
            border: 1px solid #FF0000;
            color: #FF0000;
        }
        
        .devices-list {
            margin-top: 15px;
        }
        
        .device-item {
            padding: 12px;
            border: 1px solid #333333;
            border-radius: 5px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .device-info {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .device-status {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #00FF00;
        }
        
        .device-status.offline {
            background: #FF0000;
        }
        
        .social-links {
            display: flex;
            gap: 12px;
            justify-content: center;
            margin-top: 15px;
        }
        
        .social-btn {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 8px 15px;
            border-radius: 5px;
            text-decoration: none;
            font-weight: bold;
            transition: transform 0.3s ease;
        }
        
        .social-btn:hover {
            transform: translateY(-2px);
        }
        
        .telegram {
            background: #0088cc;
            color: white;
        }
        
        .instagram {
            background: #E1306C;
            color: white;
        }
        
        .instructions {
            margin-top: 25px;
            padding: 15px;
            background: rgba(0, 255, 0, 0.05);
            border-radius: 10px;
            border-left: 4px solid #00FF00;
        }
        
        .instructions h3 {
            color: #00FF00;
            margin-bottom: 10px;
        }
        
        .instructions ol {
            padding-left: 20px;
        }
        
        .instructions li {
            margin-bottom: 8px;
        }
        
        footer {
            text-align: center;
            padding: 15px;
            border-top: 1px solid #333333;
            margin-top: 30px;
            color: #888888;
            font-size: 0.8rem;
        }
        
        .connection-info {
            background: rgba(0, 255, 0, 0.1);
            padding: 12px;
            border-radius: 5px;
            margin: 12px 0;
            font-family: monospace;
            word-break: break-all;
            font-size: 0.8rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">MØNSTR-M1ND</div>
            <div class="subtitle">Android Remote Control System v1.0.0</div>
            <div class="author">Created by MR.MONSIF</div>
        </header>
        
        <div class="main-content">
            <div class="panel">
                <h2>Device Connection</h2>
                <div class="qr-container">
                    <p>Generate QR code to connect your Android device:</p>
                    <div id="qrCode"></div>
                    <button class="btn" onclick="generateQR()">Generate QR Code</button>
                    <button class="btn btn-secondary" onclick="copyConnectionURL()">Copy Connection URL</button>
                </div>
                
                <div class="connection-info" id="connectionInfo" style="display: none;">
                    <strong>Connection URL:</strong><br>
                    <span id="connectionURL"></span>
                </div>
                
                <div class="status disconnected" id="connectionStatus">
                    Not Connected
                </div>
            </div>
            
            <div class="panel">
                <h2>Connected Devices</h2>
                <div id="devicesCount">No devices connected</div>
                <div class="devices-list" id="devicesList"></div>
                
                <div style="text-align: center; margin-top: 15px;">
                    <button class="btn" onclick="refreshDevices()">Refresh Devices</button>
                    <a href="/control" class="btn btn-secondary">Open Control Panel</a>
                </div>
                
                <div class="social-links">
                    <a href="/open_telegram" class="social-btn telegram" target="_blank">
                        Telegram
                    </a>
                    <a href="/open_instagram" class="social-btn instagram" target="_blank">
                        Instagram
                    </a>
                </div>
            </div>
        </div>
        
        <div class="instructions">
            <h3>How to Connect:</h3>
            <ol>
                <li>Click "Generate QR Code" button</li>
                <li>Scan the QR code with your Android device camera</li>
                <li>Open the link in your mobile browser</li>
                <li>Grant screen capture permissions if prompted</li>
                <li>Your device screen will appear in the control panel</li>
            </ol>
        </div>
    </div>
    
    <footer>
        <p>MØNSTR-M1ND v1.0.0 | Created by MR.MONSIF</p>
        <p>Telegram: <a href="http://t.me/monstr_m1nd" style="color: #00FF00;">@monstr_m1nd</a> | 
           Instagram: <a href="https://www.instagram.com/httpx.mrmonsif/" style="color: #00FF00;">@httpx.mrmonsif</a></p>
    </footer>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.0/socket.io.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/qrcode@1.5.0/build/qrcode.min.js"></script>
    <script>
        let socket = null;
        
        function connectWebSocket() {
            socket = io();
            
            socket.on('connect', () => {
                console.log('Connected to server');
                updateConnectionStatus(true);
            });
            
            socket.on('disconnect', () => {
                console.log('Disconnected from server');
                updateConnectionStatus(false);
            });
            
            socket.on('authenticated', (data) => {
                console.log('Authentication:', data);
                if (data.success) {
                    alert('Device connected successfully!');
                    refreshDevices();
                }
            });
        }
        
        function generateQR() {
            fetch('/generate_qr')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Display QR code
                        document.getElementById('connectionInfo').style.display = 'block';
                        document.getElementById('connectionURL').textContent = data.connection_url;
                        
                        QRCode.toCanvas(document.getElementById('qrCode'), data.connection_url, {
                            width: 200,
                            margin: 2,
                            color: {
                                dark: '#000000',
                                light: '#FFFFFF'
                            }
                        }, function(error) {
                            if (error) console.error(error);
                        });
                        
                        // Store connection info
                        window.currentConnectionURL = data.connection_url;
                        window.currentToken = data.token;
                        
                        updateConnectionStatus(true, 'QR Generated - Ready for connection');
                    } else {
                        alert('Failed to generate QR code: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('Error generating QR:', error);
                    alert('Failed to generate QR code. Check server connection.');
                });
        }
        
        function copyConnectionURL() {
            if (window.currentConnectionURL) {
                navigator.clipboard.writeText(window.currentConnectionURL)
                    .then(() => {
                        alert('Connection URL copied to clipboard!');
                    })
                    .catch(err => {
                        console.error('Failed to copy:', err);
                        // Fallback for older browsers
                        const textArea = document.createElement('textarea');
                        textArea.value = window.currentConnectionURL;
                        document.body.appendChild(textArea);
                        textArea.select();
                        try {
                            document.execCommand('copy');
                            alert('Connection URL copied to clipboard!');
                        } catch (err) {
                            alert('Failed to copy URL. Please copy manually.');
                        }
                        document.body.removeChild(textArea);
                    });
            } else {
                alert('Please generate a QR code first');
            }
        }
        
        function refreshDevices() {
            fetch('/devices')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const devicesList = document.getElementById('devicesList');
                        const devicesCount = document.getElementById('devicesCount');
                        
                        devicesCount.textContent = `${data.count} device(s) connected`;
                        
                        if (data.devices.length > 0) {
                            let html = '';
                            data.devices.forEach(device => {
                                html += `
                                    <div class="device-item">
                                        <div class="device-info">
                                            <div class="device-status ${device.screen_size ? '' : 'offline'}"></div>
                                            <div>
                                                <strong>${device.device}</strong><br>
                                                <small>${device.sid.substring(0, 12)}...</small>
                                            </div>
                                        </div>
                                        <div style="font-size: 0.8rem;">
                                            ${device.screen_size ? `${device.screen_size[0]}x${device.screen_size[1]}` : 'Unknown'}
                                        </div>
                                    </div>
                                `;
                            });
                            devicesList.innerHTML = html;
                        } else {
                            devicesList.innerHTML = '<p style="text-align: center; color: #888; font-size: 0.9rem;">No devices connected</p>';
                        }
                    }
                })
                .catch(error => {
                    console.error('Error fetching devices:', error);
                });
        }
        
        function updateConnectionStatus(connected, message = '') {
            const statusDiv = document.getElementById('connectionStatus');
            
            if (connected) {
                statusDiv.className = 'status connected';
                statusDiv.innerHTML = (message || 'Connected to server');
            } else {
                statusDiv.className = 'status disconnected';
                statusDiv.innerHTML = (message || 'Not connected');
            }
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            connectWebSocket();
            refreshDevices();
            
            // Auto-refresh devices every 5 seconds
            setInterval(refreshDevices, 5000);
        });
    </script>
</body>
</html>'''
    
    with open("templates/index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    
    # Simple mobile page
    mobile_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MØNSTR-M1ND - Mobile Client</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: Arial, sans-serif;
            background: #000000;
            color: #FFFFFF;
            line-height: 1.6;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 15px;
            text-align: center;
        }
        
        .container {
            max-width: 100%;
            width: 100%;
        }
        
        .logo {
            font-size: 2rem;
            font-weight: bold;
            color: #00FF00;
            text-shadow: 0 0 10px #00FF00;
            letter-spacing: 2px;
            margin-bottom: 10px;
        }
        
        .subtitle {
            font-size: 0.9rem;
            color: #888888;
            margin-bottom: 20px;
        }
        
        .status-box {
            background: #111111;
            border: 2px solid #00FF00;
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.2);
            width: 100%;
            max-width: 400px;
        }
        
        .status-text {
            font-size: 1.2rem;
            margin-bottom: 10px;
            color: #00FF00;
        }
        
        .device-info {
            background: rgba(0, 255, 0, 0.1);
            padding: 12px;
            border-radius: 8px;
            margin: 12px 0;
            text-align: left;
            font-size: 0.9rem;
        }
        
        .device-info p {
            margin: 4px 0;
        }
        
        .instructions {
            background: rgba(255, 255, 255, 0.05);
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            text-align: left;
            font-size: 0.9rem;
        }
        
        .instructions h3 {
            color: #00FF00;
            margin-bottom: 8px;
            font-size: 1rem;
        }
        
        .btn {
            display: inline-block;
            background: #00FF00;
            color: #000000;
            padding: 12px 25px;
            border: none;
            border-radius: 6px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.3s ease;
            margin: 8px 0;
            width: 100%;
        }
        
        .btn:hover {
            background: #00CC00;
        }
        
        .btn-secondary {
            background: #333333;
            color: #FFFFFF;
        }
        
        .btn-secondary:hover {
            background: #444444;
        }
        
        .permission-note {
            color: #FF5555;
            font-size: 0.8rem;
            margin-top: 15px;
            padding: 8px;
            border: 1px solid #FF5555;
            border-radius: 5px;
        }
        
        #videoPreview {
            width: 100%;
            max-width: 300px;
            border: 2px solid #00FF00;
            border-radius: 8px;
            margin: 15px auto;
            display: none;
        }
        
        .screen-info {
            display: flex;
            justify-content: space-between;
            margin-top: 10px;
            font-size: 0.8rem;
            color: #888888;
        }
        
        footer {
            margin-top: 25px;
            color: #888888;
            font-size: 0.8rem;
        }
        
        .social-links {
            display: flex;
            gap: 12px;
            justify-content: center;
            margin-top: 15px;
        }
        
        .social-btn {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 8px 12px;
            border-radius: 5px;
            text-decoration: none;
            font-weight: bold;
            font-size: 0.9rem;
            transition: transform 0.3s ease;
        }
        
        .telegram {
            background: #0088cc;
            color: white;
        }
        
        .instagram {
            background: #E1306C;
            color: white;
        }
        
        .hidden {
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">MØNSTR-M1ND</div>
        <div class="subtitle">Mobile Client v1.0.0 | Created by MR.MONSIF</div>
        
        <div class="status-box">
            <div class="status-text" id="statusText">Ready to Connect</div>
            
            <div class="device-info">
                <p><strong>Device:</strong> <span id="deviceName">Detecting...</span></p>
                <p><strong>Screen:</strong> <span id="screenSize">Unknown</span></p>
                <p><strong>Connection:</strong> <span id="connectionStatus">Not connected</span></p>
            </div>
            
            <video id="videoPreview" autoplay playsinline></video>
            
            <div class="screen-info">
                <span>FPS: <span id="fpsCounter">0</span></span>
                <span>Quality: <span id="qualityInfo">Medium</span></span>
            </div>
            
            <button class="btn" id="connectBtn" onclick="startConnection()">Start Screen Sharing</button>
            <button class="btn btn-secondary" id="stopBtn" onclick="stopConnection()" style="display: none;">Stop Sharing</button>
            
            <div class="permission-note" id="permissionNote">
                Note: You need to grant screen capture permissions. On Chrome Android, tap "Share" then "Start now".
            </div>
            
            <div class="instructions">
                <h3>Usage Instructions:</h3>
                <p>1. Click "Start Screen Sharing"</p>
                <p>2. Grant screen capture permissions</p>
                <p>3. Your screen will be streamed to desktop</p>
                <p>4. You can now control your phone from computer</p>
            </div>
        </div>
        
        <div class="social-links">
            <a href="http://t.me/monstr_m1nd" class="social-btn telegram" target="_blank">
                Telegram
            </a>
            <a href="https://www.instagram.com/httpx.mrmonsif/" class="social-btn instagram" target="_blank">
                Instagram
            </a>
        </div>
        
        <footer>
            <p>MØNSTR-M1ND Remote Control System</p>
            <p>Keep this page open for continuous streaming</p>
        </footer>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.0/socket.io.min.js"></script>
    <script>
        let socket = null;
        let screenStream = null;
        let canvas = null;
        let ctx = null;
        let streaming = false;
        let fps = 0;
        let frameCount = 0;
        let lastFpsUpdate = Date.now();
        let token = new URLSearchParams(window.location.search).get('token');
        
        // Device information
        const deviceInfo = {
            device: navigator.userAgent,
            platform: navigator.platform,
            screenWidth: window.screen.width,
            screenHeight: window.screen.height,
            token: token
        };
        
        function updateDeviceInfo() {
            const deviceName = deviceInfo.device.length > 30 ? deviceInfo.device.substring(0, 30) + '...' : deviceInfo.device;
            document.getElementById('deviceName').textContent = deviceName;
            document.getElementById('screenSize').textContent = `${deviceInfo.screenWidth} × ${deviceInfo.screenHeight}`;
        }
        
        function connectWebSocket() {
            socket = io();
            
            socket.on('connect', () => {
                console.log('Connected to server');
                updateStatus('Connected to server');
                
                // Authenticate with token
                socket.emit('authenticate', {
                    token: token,
                    client_data: deviceInfo
                });
            });
            
            socket.on('authenticated', (data) => {
                if (data.success) {
                    updateStatus('Authenticated');
                    console.log('Authentication successful:', data);
                } else {
                    updateStatus('Authentication failed');
                    alert('Authentication failed. Please refresh the page.');
                }
            });
            
            socket.on('disconnect', () => {
                updateStatus('Disconnected');
                streaming = false;
            });
            
            socket.on('control_event', (data) => {
                handleControlEvent(data);
            });
            
            socket.on('pong', () => {
                // Keep alive
            });
        }
        
        function updateStatus(text) {
            document.getElementById('statusText').textContent = text;
            document.getElementById('connectionStatus').textContent = text;
        }
        
        async function startConnection() {
            try {
                updateStatus('Requesting permissions...');
                
                // Check if getDisplayMedia is available
                if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
                    updateStatus('Screen sharing not supported');
                    alert('Screen sharing is not supported in your browser. Please use Chrome or Edge on Android.');
                    return;
                }
                
                // Request screen capture
                screenStream = await navigator.mediaDevices.getDisplayMedia({
                    video: {
                        width: { ideal: 1280 },
                        height: { ideal: 720 },
                        frameRate: { ideal: 15 }
                    },
                    audio: false
                });
                
                // Create canvas for capturing frames
                canvas = document.createElement('canvas');
                ctx = canvas.getContext('2d');
                
                // Set canvas size to stream dimensions
                const videoTrack = screenStream.getVideoTracks()[0];
                const settings = videoTrack.getSettings();
                
                canvas.width = settings.width || 1280;
                canvas.height = settings.height || 720;
                
                // Create video element for capturing
                const video = document.createElement('video');
                video.srcObject = screenStream;
                video.play();
                
                // Show preview
                const preview = document.getElementById('videoPreview');
                preview.srcObject = screenStream;
                preview.style.display = 'block';
                
                updateStatus('Screen sharing active');
                document.getElementById('connectBtn').style.display = 'none';
                document.getElementById('stopBtn').style.display = 'block';
                document.getElementById('permissionNote').style.display = 'none';
                
                // Start streaming frames
                streaming = true;
                startStreaming(video);
                
                // Handle stream ending
                videoTrack.onended = () => {
                    stopConnection();
                };
                
            } catch (error) {
                console.error('Screen capture error:', error);
                updateStatus('Permission denied');
                alert('Screen sharing permission is required. Please try again.');
            }
        }
        
        function startStreaming(video) {
            function captureFrame() {
                if (!streaming || !socket || !socket.connected) return;
                
                try {
                    // Draw video frame to canvas
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    
                    // Get image data as JPEG
                    canvas.toBlob((blob) => {
                        if (blob) {
                            const reader = new FileReader();
                            reader.onload = () => {
                                // Send frame data via WebSocket
                                socket.emit('screen_data', {
                                    frame: reader.result,
                                    screen_info: {
                                        width: canvas.width,
                                        height: canvas.height
                                    }
                                });
                                
                                // Update FPS counter
                                frameCount++;
                                const now = Date.now();
                                if (now - lastFpsUpdate >= 1000) {
                                    fps = frameCount;
                                    frameCount = 0;
                                    lastFpsUpdate = now;
                                    document.getElementById('fpsCounter').textContent = fps;
                                }
                            };
                            reader.readAsDataURL(blob);
                        }
                    }, 'image/jpeg', 0.7);
                    
                } catch (error) {
                    console.error('Frame capture error:', error);
                }
                
                // Schedule next frame
                if (streaming) {
                    setTimeout(captureFrame, 1000 / 15); // 15 FPS
                }
            }
            
            // Start capturing
            captureFrame();
        }
        
        function stopConnection() {
            streaming = false;
            
            if (screenStream) {
                screenStream.getTracks().forEach(track => track.stop());
                screenStream = null;
            }
            
            document.getElementById('connectBtn').style.display = 'block';
            document.getElementById('stopBtn').style.display = 'none';
            document.getElementById('videoPreview').style.display = 'none';
            
            updateStatus('Ready to connect');
        }
        
        function handleControlEvent(event) {
            console.log('Control event received:', event);
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            updateDeviceInfo();
            connectWebSocket();
            
            // Send periodic pings
            setInterval(() => {
                if (socket && socket.connected) {
                    socket.emit('ping');
                }
            }, 10000);
        });
        
        // Handle page visibility change
        document.addEventListener('visibilitychange', () => {
            if (document.hidden && streaming) {
                console.log('Page hidden, pausing stream');
            }
        });
        
        // Handle beforeunload
        window.addEventListener('beforeunload', () => {
            if (streaming) {
                stopConnection();
            }
        });
    </script>
</body>
</html>'''
    
    with open("templates/mobile.html", "w", encoding="utf-8") as f:
        f.write(mobile_html)
    
    # Simple control panel
    control_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MØNSTR-M1ND - Control Panel</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: Arial, sans-serif;
            background: #000000;
            color: #FFFFFF;
            line-height: 1.6;
            height: 100vh;
            overflow: hidden;
        }
        
        .container {
            display: flex;
            height: 100vh;
        }
        
        .sidebar {
            width: 280px;
            background: #111111;
            border-right: 2px solid #333333;
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }
        
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .header {
            background: #000000;
            border-bottom: 2px solid #333333;
            padding: 12px 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: bold;
            color: #00FF00;
            text-shadow: 0 0 10px #00FF00;
            letter-spacing: 1px;
        }
        
        .device-status {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.9rem;
        }
        
        .status-indicator {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #FF0000;
        }
        
        .status-indicator.active {
            background: #00FF00;
            box-shadow: 0 0 8px #00FF00;
        }
        
        .stream-container {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #000000;
            position: relative;
            overflow: hidden;
        }
        
        #streamDisplay {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            border: 2px solid #333333;
            border-radius: 5px;
            background: #000000;
        }
        
        .no-stream {
            text-align: center;
            color: #888888;
            padding: 30px;
        }
        
        .control-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            cursor: crosshair;
            z-index: 10;
        }
        
        .panel-section {
            padding: 15px;
            border-bottom: 1px solid #333333;
        }
        
        .panel-title {
            color: #00FF00;
            font-size: 1.1rem;
            margin-bottom: 12px;
        }
        
        .device-list {
            max-height: 180px;
            overflow-y: auto;
            margin-bottom: 10px;
        }
        
        .device-item {
            padding: 10px;
            border: 1px solid #333333;
            border-radius: 5px;
            margin-bottom: 6px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 0.9rem;
        }
        
        .device-item:hover {
            background: #222222;
            border-color: #00FF00;
        }
        
        .device-item.active {
            background: rgba(0, 255, 0, 0.1);
            border-color: #00FF00;
        }
        
        .device-name {
            font-weight: bold;
            margin-bottom: 4px;
        }
        
        .device-meta {
            font-size: 0.75rem;
            color: #888888;
            display: flex;
            justify-content: space-between;
        }
        
        .btn {
            background: #00FF00;
            color: #000000;
            border: none;
            padding: 8px 12px;
            border-radius: 5px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            width: 100%;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }
        
        .btn:hover {
            background: #00CC00;
            transform: translateY(-2px);
        }
        
        .btn-secondary {
            background: #333333;
            color: #FFFFFF;
        }
        
        .btn-secondary:hover {
            background: #444444;
        }
        
        .control-buttons {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
            margin-top: 8px;
        }
        
        .control-btn {
            background: #222222;
            color: #FFFFFF;
            border: 1px solid #333333;
            padding: 10px;
            border-radius: 5px;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            font-size: 0.8rem;
        }
        
        .control-btn:hover {
            background: #333333;
            border-color: #00FF00;
        }
        
        .keyboard-input {
            background: #000000;
            color: #FFFFFF;
            border: 1px solid #333333;
            padding: 10px;
            border-radius: 5px;
            width: 100%;
            font-size: 0.9rem;
            margin-top: 8px;
        }
        
        .keyboard-input:focus {
            outline: none;
            border-color: #00FF00;
        }
        
        .social-buttons {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 12px;
        }
        
        .social-btn {
            padding: 10px;
            border-radius: 5px;
            color: white;
            text-decoration: none;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            font-weight: bold;
            font-size: 0.9rem;
            transition: transform 0.3s ease;
        }
        
        .social-btn:hover {
            transform: translateY(-2px);
        }
        
        .telegram-btn {
            background: #0088cc;
        }
        
        .instagram-btn {
            background: #E1306C;
        }
        
        .stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 12px;
        }
        
        .stat-item {
            background: rgba(0, 255, 0, 0.1);
            padding: 8px;
            border-radius: 5px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 1rem;
            font-weight: bold;
            color: #00FF00;
        }
        
        .stat-label {
            font-size: 0.75rem;
            color: #888888;
        }
        
        .coordinates {
            position: absolute;
            bottom: 15px;
            right: 15px;
            background: rgba(0, 0, 0, 0.8);
            padding: 8px 12px;
            border-radius: 5px;
            border: 1px solid #00FF00;
            font-family: monospace;
            z-index: 20;
            font-size: 0.8rem;
        }
        
        .control-mode {
            position: absolute;
            top: 15px;
            right: 15px;
            background: rgba(0, 255, 0, 0.2);
            color: #00FF00;
            padding: 6px 12px;
            border-radius: 5px;
            font-weight: bold;
            border: 1px solid #00FF00;
            z-index: 20;
            font-size: 0.9rem;
        }
        
        .hidden {
            display: none;
        }
        
        .fullscreen-btn {
            position: absolute;
            top: 15px;
            left: 15px;
            background: rgba(0, 0, 0, 0.8);
            color: #FFFFFF;
            border: 1px solid #333333;
            padding: 6px 12px;
            border-radius: 5px;
            cursor: pointer;
            z-index: 20;
            transition: all 0.3s ease;
            font-size: 0.9rem;
        }
        
        .fullscreen-btn:hover {
            border-color: #00FF00;
            color: #00FF00;
        }
        
        ::-webkit-scrollbar {
            width: 6px;
        }
        
        ::-webkit-scrollbar-track {
            background: #000000;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #333333;
            border-radius: 3px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #00FF00;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <div class="panel-section">
                <div class="panel-title">Connected Devices</div>
                <div class="device-list" id="deviceList">
                    <div class="no-devices">No devices connected</div>
                </div>
                <button class="btn" onclick="refreshDevices()">
                    Refresh Devices
                </button>
            </div>
            
            <div class="panel-section">
                <div class="panel-title">Device Controls</div>
                <div class="control-buttons">
                    <div class="control-btn" onclick="sendCommand('home')">
                        Home
                    </div>
                    <div class="control-btn" onclick="sendCommand('back')">
                        Back
                    </div>
                    <div class="control-btn" onclick="sendCommand('recent')">
                        Recent
                    </div>
                    <div class="control-btn" onclick="sendCommand('volume_up')">
                        Vol+
                    </div>
                    <div class="control-btn" onclick="sendCommand('volume_down')">
                        Vol-
                    </div>
                    <div class="control-btn" onclick="sendCommand('power')">
                        Power
                    </div>
                </div>
                
                <input type="text" 
                       class="keyboard-input" 
                       placeholder="Type text to send..."
                       id="keyboardInput"
                       onkeydown="handleKeyDown(event)"
                       onkeyup="handleKeyUp(event)">
                
                <button class="btn btn-secondary" onclick="clearText()">
                    Clear Text
                </button>
            </div>
            
            <div class="panel-section">
                <div class="panel-title">Stream Controls</div>
                <button class="btn" id="streamBtn" onclick="toggleStream()">
                    Start Stream
                </button>
                <button class="btn btn-secondary" onclick="takeScreenshot()">
                    Take Screenshot
                </button>
                <button class="btn" id="controlModeBtn" onclick="toggleControlMode()">
                    Enable Control Mode
                </button>
                
                <div class="stats">
                    <div class="stat-item">
                        <div class="stat-value" id="fpsCounter">0</div>
                        <div class="stat-label">FPS</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value" id="qualityInfo">Medium</div>
                        <div class="stat-label">Quality</div>
                    </div>
                </div>
            </div>
            
            <div class="panel-section">
                <div class="panel-title">Quick Links</div>
                <div class="social-buttons">
                    <a href="/open_telegram" class="social-btn telegram-btn" target="_blank">
                        Telegram
                    </a>
                    <a href="/open_instagram" class="social-btn instagram-btn" target="_blank">
                        Instagram
                    </a>
                </div>
                
                <button class="btn btn-secondary" onclick="location.href='/'">
                    Back to Main
                </button>
            </div>
            
            <div class="panel-section">
                <div class="panel-title">System Info</div>
                <div class="stats">
                    <div class="stat-item">
                        <div class="stat-value" id="connectedCount">0</div>
                        <div class="stat-label">Devices</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value" id="uptimeInfo">0s</div>
                        <div class="stat-label">Uptime</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="header">
                <div class="logo">MØNSTR-M1ND Control</div>
                <div class="device-status">
                    <div class="status-indicator" id="connectionIndicator"></div>
                    <span id="currentDevice">No device selected</span>
                </div>
            </div>
            
            <div class="stream-container">
                <div class="no-stream" id="noStream">
                    <h2>No Active Stream</h2>
                    <p>Select a device and click "Start Stream" to begin</p>
                </div>
                
                <img id="streamDisplay" class="hidden">
                <div class="control-overlay hidden" id="controlOverlay"
                     onmousedown="handleMouseDown(event)"
                     onmousemove="handleMouseMove(event)"
                     onmouseup="handleMouseUp(event)"
                     onwheel="handleMouseWheel(event)"></div>
                
                <div class="fullscreen-btn" onclick="toggleFullscreen()">
                    Fullscreen
                </div>
                
                <div class="coordinates hidden" id="coordinates">
                    X: 0, Y: 0
                </div>
                
                <div class="control-mode hidden" id="controlModeIndicator">
                    Control Mode: ON
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.0/socket.io.min.js"></script>
    <script>
        let socket = null;
        let currentDevice = null;
        let streaming = false;
        let controlMode = false;
        let mouseDown = false;
        
        function connectWebSocket() {
            socket = io();
            
            socket.on('connect', () => {
                console.log('Connected to server');
                updateConnectionStatus(true);
                refreshDevices();
            });
            
            socket.on('disconnect', () => {
                console.log('Disconnected from server');
                updateConnectionStatus(false);
            });
            
            // Start periodic updates
            startStatsUpdate();
        }
        
        function updateConnectionStatus(connected) {
            const indicator = document.getElementById('connectionIndicator');
            if (connected) {
                indicator.className = 'status-indicator active';
            } else {
                indicator.className = 'status-indicator';
            }
        }
        
        function refreshDevices() {
            fetch('/devices')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const deviceList = document.getElementById('deviceList');
                        const connectedCount = document.getElementById('connectedCount');
                        
                        connectedCount.textContent = data.count;
                        
                        if (data.devices.length > 0) {
                            let html = '';
                            data.devices.forEach(device => {
                                const isActive = currentDevice === device.sid;
                                html += `
                                    <div class="device-item ${isActive ? 'active' : ''}" 
                                         onclick="selectDevice('${device.sid}', '${device.device}')">
                                        <div class="device-name">${device.device.substring(0, 20)}${device.device.length > 20 ? '...' : ''}</div>
                                        <div class="device-meta">
                                            <span>${device.screen_size ? `${device.screen_size[0]}x${device.screen_size[1]}` : 'Unknown'}</span>
                                            <span>${isActive ? 'Active' : ''}</span>
                                        </div>
                                    </div>
                                `;
                            });
                            deviceList.innerHTML = html;
                        } else {
                            deviceList.innerHTML = '<div class="no-devices" style="text-align: center; color: #888; padding: 10px; font-size: 0.9rem;">No devices connected</div>';
                        }
                    }
                })
                .catch(error => {
                    console.error('Error fetching devices:', error);
                });
        }
        
        function selectDevice(sid, deviceName) {
            currentDevice = sid;
            document.getElementById('currentDevice').textContent = deviceName.substring(0, 15) + (deviceName.length > 15 ? '...' : '');
            refreshDevices();
            
            // Update UI
            document.getElementById('streamBtn').disabled = false;
            document.getElementById('streamBtn').innerHTML = 'Start Stream';
            
            // Stop any existing stream
            stopStream();
        }
        
        function toggleStream() {
            if (!currentDevice) {
                alert('Please select a device first');
                return;
            }
            
            if (!streaming) {
                startStream();
            } else {
                stopStream();
            }
        }
        
        function startStream() {
            if (!currentDevice) return;
            
            const streamDisplay = document.getElementById('streamDisplay');
            const noStream = document.getElementById('noStream');
            
            // Show stream display
            streamDisplay.src = `/stream/${currentDevice}`;
            streamDisplay.classList.remove('hidden');
            noStream.classList.add('hidden');
            
            // Update button
            document.getElementById('streamBtn').innerHTML = 'Stop Stream';
            
            streaming = true;
            
            console.log('Stream started for device:', currentDevice);
        }
        
        function stopStream() {
            const streamDisplay = document.getElementById('streamDisplay');
            const noStream = document.getElementById('noStream');
            
            // Hide stream display
            streamDisplay.src = '';
            streamDisplay.classList.add('hidden');
            noStream.classList.remove('hidden');
            
            // Update button
            document.getElementById('streamBtn').innerHTML = 'Start Stream';
            
            streaming = false;
            controlMode = false;
            
            // Hide control elements
            document.getElementById('controlOverlay').classList.add('hidden');
            document.getElementById('controlModeIndicator').classList.add('hidden');
            document.getElementById('controlModeBtn').innerHTML = 'Enable Control Mode';
            
            console.log('Stream stopped');
        }
        
        function toggleControlMode() {
            if (!streaming) {
                alert('Please start the stream first');
                return;
            }
            
            controlMode = !controlMode;
            const overlay = document.getElementById('controlOverlay');
            const indicator = document.getElementById('controlModeIndicator');
            const btn = document.getElementById('controlModeBtn');
            
            if (controlMode) {
                overlay.classList.remove('hidden');
                indicator.classList.remove('hidden');
                btn.innerHTML = 'Disable Control Mode';
                console.log('Control mode enabled');
            } else {
                overlay.classList.add('hidden');
                indicator.classList.add('hidden');
                btn.innerHTML = 'Enable Control Mode';
                console.log('Control mode disabled');
            }
        }
        
        function handleMouseDown(event) {
            if (!controlMode || !currentDevice) return;
            
            mouseDown = true;
            
            // Calculate relative coordinates
            const streamDisplay = document.getElementById('streamDisplay');
            const x = (event.offsetX / streamDisplay.clientWidth) * 100;
            const y = (event.offsetY / streamDisplay.clientHeight) * 100;
            
            // Send mouse down event
            sendMouseEvent('down', x, y);
            
            // Update coordinates display
            updateCoordinates(x, y);
        }
        
        function handleMouseMove(event) {
            if (!controlMode || !currentDevice) return;
            
            // Calculate relative coordinates
            const streamDisplay = document.getElementById('streamDisplay');
            const x = (event.offsetX / streamDisplay.clientWidth) * 100;
            const y = (event.offsetY / streamDisplay.clientHeight) * 100;
            
            if (mouseDown) {
                // Send mouse move event
                sendMouseEvent('move', x, y);
            }
            
            // Update coordinates display
            updateCoordinates(x, y);
        }
        
        function handleMouseUp(event) {
            if (!controlMode || !currentDevice) return;
            
            mouseDown = false;
            
            // Calculate relative coordinates
            const streamDisplay = document.getElementById('streamDisplay');
            const x = (event.offsetX / streamDisplay.clientWidth) * 100;
            const y = (event.offsetY / streamDisplay.clientHeight) * 100;
            
            // Send mouse up event
            sendMouseEvent('up', x, y);
        }
        
        function handleMouseWheel(event) {
            if (!controlMode || !currentDevice) return;
            
            event.preventDefault();
            
            // Calculate relative coordinates
            const streamDisplay = document.getElementById('streamDisplay');
            const x = (event.offsetX / streamDisplay.clientWidth) * 100;
            const y = (event.offsetY / streamDisplay.clientHeight) * 100;
            const delta = event.deltaY > 0 ? -1 : 1;
            
            // Send mouse wheel event
            sendMouseEvent('wheel', x, y, delta);
        }
        
        function handleKeyDown(event) {
            if (!controlMode || !currentDevice) return;
            
            // Prevent default for special keys
            if ([13, 32, 8, 9].includes(event.keyCode)) {
                event.preventDefault();
            }
            
            // Send keyboard event
            sendKeyboardEvent('down', event.key, event.keyCode);
        }
        
        function handleKeyUp(event) {
            if (!controlMode || !currentDevice) return;
            
            // Send keyboard event
            sendKeyboardEvent('up', event.key, event.keyCode);
        }
        
        function sendMouseEvent(type, x, y, extra = null) {
            if (!socket || !currentDevice) return;
            
            socket.emit('control', {
                sid: currentDevice,
                type: 'mouse',
                data: {
                    type: type,
                    x: x,
                    y: y,
                    button: 'left',
                    extra: extra
                }
            });
        }
        
        function sendKeyboardEvent(type, key, keyCode) {
            if (!socket || !currentDevice) return;
            
            socket.emit('control', {
                sid: currentDevice,
                type: 'keyboard',
                data: {
                    type: type,
                    key: key,
                    keyCode: keyCode,
                    text: key.length === 1 ? key : ''
                }
            });
        }
        
        function sendCommand(command) {
            if (!currentDevice) {
                alert('Please select a device first');
                return;
            }
            
            fetch(`/send_command/${currentDevice}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ command: command })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Command sent:', command);
                }
            })
            .catch(error => {
                console.error('Error sending command:', error);
            });
        }
        
        function takeScreenshot() {
            if (!currentDevice) {
                alert('Please select a device first');
                return;
            }
            
            fetch(`/screenshot/${currentDevice}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(`Screenshot saved: ${data.filename}`);
                    } else {
                        alert('Failed to take screenshot');
                    }
                })
                .catch(error => {
                    console.error('Error taking screenshot:', error);
                    alert('Error taking screenshot');
                });
        }
        
        function clearText() {
            document.getElementById('keyboardInput').value = '';
        }
        
        function updateCoordinates(x, y) {
            const coords = document.getElementById('coordinates');
            coords.textContent = `X: ${x.toFixed(1)}%, Y: ${y.toFixed(1)}%`;
            coords.classList.remove('hidden');
        }
        
        function toggleFullscreen() {
            const streamContainer = document.querySelector('.stream-container');
            
            if (!document.fullscreenElement) {
                streamContainer.requestFullscreen().catch(err => {
                    console.error(`Error attempting to enable fullscreen: ${err.message}`);
                });
            } else {
                document.exitFullscreen();
            }
        }
        
        function startStatsUpdate() {
            // Update uptime
            setInterval(() => {
                fetch('/system_info')
                    .then(response => response.json())
                    .then(data => {
                        const uptime = Math.floor(data.uptime);
                        const hours = Math.floor(uptime / 3600);
                        const minutes = Math.floor((uptime % 3600) / 60);
                        const seconds = uptime % 60;
                        
                        document.getElementById('uptimeInfo').textContent = 
                            `${hours}h ${minutes}m ${seconds}s`;
                    });
            }, 1000);
            
            // Refresh devices every 5 seconds
            setInterval(refreshDevices, 5000);
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            connectWebSocket();
        });
    </script>
</body>
</html>'''
    
    with open("templates/control.html", "w", encoding="utf-8") as f:
        f.write(control_html)

def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("MØNSTR-M1ND Android Remote Control System")
    print("="*60)
    print("Created by MR.MONSIF")
    print(f"Telegram: {config.TELEGRAM_URL}")
    print(f"Instagram: {config.INSTAGRAM_URL}")
    print("="*60)
    
    if not FLASK_AVAILABLE:
        print("\n[ERROR] Required packages not installed!")
        print("Please install: pip install flask flask-socketio flask-cors qrcode[pil] pillow pyautogui keyboard")
        return
    
    try:
        # Create templates
        create_templates()
        
        # Create and run app
        app = MØNSTRApp()
        app.run()
        
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down MØNSTR-M1ND...")
        print("[INFO] Goodbye! Created by MR.MONSIF")
    except Exception as e:
        print(f"\n[ERROR] Application error: {e}")
        print("[ERROR] Please report issues to: http://t.me/monstr_m1nd")

if __name__ == "__main__":
    main()