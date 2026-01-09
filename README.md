# MØNSTR-M1ND

**Android Remote Control System (QR Based)**

A professional proof-of-concept system that allows controlling and viewing an Android device screen from a desktop using **Python only on the computer** with QR Code–based connection

---

## Features

 QR Code–based connection (no cable)
 Live screen streaming from Android to Desktop
 Desktop control panel
 Mouse events (click + move + drag)
 Keyboard input events
 Token-based authentication
 WebSocket real-time communication
 No Android app required (browser-based client)

> ⚠️ Note: This project is a **Proof of Concept**
> Full physical control on Android is limited by browser and OS security

---

## Requirements

### System

* Windows / Linux
* Python **3.9+**
* Android phone with:

  * Chrome / Edge browser
  * Screen sharing support

---

## Python Libraries

Install all required dependencies using:

```bash
pip install flask flask-socketio flask-cors qrcode[pil] pillow pyautogui keyboard
```

### Libraries Used

* `flask` – web server
* `flask-socketio` – real-time communication
* `flask-cors` – cross-origin support
* `qrcode[pil]` – QR code generation
* `pillow` – image processing
* `pyautogui` – desktop input handling
* `keyboard` – keyboard event capture

---

## Project Structure

```
MØNSTR-M1ND/
│
├── monstr_m1nd.py        # Main application
├── templates/
│   ├── index.html        # Main interface
│   ├── mobile.html       # Android browser client
│   └── control.html      # Desktop control panel
│
├── static/
│   └── qrcodes/          # Generated QR codes
│
├── screenshots/          # Captured screenshots
└── qrcodes/              # Raw QR images
```

---

## How to Run

1. Clone the repository:

```bash
git clone https://github.com/yourusername/monstr-m1nd.git
cd monstr-m1nd
```

2. Run the server:

```bash
python monstr_m1nd.py
```

3. Open in your desktop browser:

```
http://localhost:5000
```

---

## How to Use

1. Open the main interface on your computer
2. Click **Generate QR Code**
3. Scan the QR code with your Android phone
4. Open the link in the phone browser
5. Grant screen sharing permission
6. Open **Control Panel** on desktop
7. Start stream and control the device

---

## Control Notes

* Mouse clicks are mapped proportionally to phone screen
* Keyboard input is sent as events
* Control is **logical**, not system-level
* Some Android actions may not respond due to OS limitations

---

## Limitations (Important)

* Browser **cannot inject real touch events** into Android system
* Full control requires:

  * ADB connection **or**
  * Android Accessibility Service (not included)

This project intentionally avoids those to stay:

* Python-only on desktop
* App-free on Android

---

## Intended Use

* Educational purposes
* Proof of concept
* Networking & real-time systems demo
* Portfolio / research project

---

## Author

**MR MONSIF**

* Telegram: [http://t.me/monstr_m1nd](http://t.me/monstr_m1nd)
* Instagram: [https://www.instagram.com/httpx.mrmonsif/](https://www.instagram.com/httpx.mrmonsif/)

---

## License

This project is provided **as-is** for educational and research purposes
You are responsible for how you use or modify it......................
