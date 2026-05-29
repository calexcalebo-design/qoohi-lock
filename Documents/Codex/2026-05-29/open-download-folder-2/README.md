# QOOHI

A small local Python cyber cafe timer. The operator page starts paid sessions for customer PCs. Customer screens show remaining time and lock when time expires.

## Run

Install Python 3, then run:

```powershell
python app.py
```

Open the operator page:

```text
http://127.0.0.1:8080/admin
```

Default admin PIN:

```text
1234
```

To use a different PIN:

```powershell
$env:CAFE_ADMIN_PIN = "9090"
python app.py
```

From another customer PC on the same Wi-Fi/LAN, use the server PC IP address instead of `127.0.0.1`, for example:

```text
http://192.168.1.20:8080/customer/1
```

## Add a customer PC

1. Log in to `/admin`.
2. Type the PC name and its LAN IP address, for example `192.168.1.25`.
3. Click **Add PC**.
4. Use **Start** to begin the paid time. The customer timer updates automatically every second.

## Customer lock agent

The browser customer page can show time and messages, but a customer can close a normal browser. For stronger locking, run `customer_agent.py` on each customer Windows PC.

Example for PC 1, when the admin/server PC IP is `192.168.1.20`:

```powershell
python customer_agent.py http://192.168.1.20:8080 1
```

When time is active, the agent shows a small always-on-top timer bar. When time is expired, stopped, or the server cannot be reached, it automatically changes to a full-screen lock.

For real-world use, put this agent in Windows startup and use standard customer accounts without Administrator rights.

## Prices

The starter prices are in `app.py`:

- 10 KSh = 10 minutes
- 50 KSh = 1 hour

## Important

The customer agent is a starter lock. A determined customer with Administrator access can bypass it. For real cyber cafe control, use Windows standard accounts, block Task Manager and Settings, prevent USB boot in BIOS, and run the agent at startup.

## Blocking adult content

Do this at the router/DNS level so it applies to every browser and app:

- Set router DNS to Cloudflare Family DNS: `1.1.1.3` and `1.0.0.3`
- Or use OpenDNS FamilyShield: `208.67.222.123` and `208.67.220.123`
- Lock customer PCs so customers cannot change DNS settings.

This is much stronger than trying to block adult sites inside this app.
