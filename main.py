import asyncio
import random
import ssl
import json
import time
import uuid
from loguru import logger
from websockets_proxy import Proxy, proxy_connect

URILIST = [
    "ws://proxy2.wynd.network:80/",
    "wss://proxy2.wynd.network:443/",
    "wss://proxy2.wynd.network:4650/",
    "wss://proxy2.wynd.network:4444/",
    "wss://proxy2.wynd.network:0/"
]

async def connect_to_wss(proxy, user_id, uri):
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, proxy))
    ssl_context = None

    if uri.startswith("wss://"):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    custom_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }

    logger.info(f"Proxy {proxy} Attempting connection to {uri}")

    try:
        proxy_obj = Proxy.from_url(proxy)
        async with proxy_connect(uri, proxy=proxy_obj, ssl=ssl_context, extra_headers={
            "Origin": "chrome-extension://lkbnfiajjmbhnfledhphioinpickokdi",
            "User-Agent": custom_headers["User-Agent"]
        }) as websocket:
            
            async def send_ping():
                while True:
                    send_message = json.dumps({"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}})
                    logger.debug(send_message)
                    await websocket.send(send_message)
                    await asyncio.sleep(110)

            send_ping_task = asyncio.create_task(send_ping())

            try:
                while True:
                    response = await websocket.recv()
                    message = json.loads(response)
                    logger.info(message)

                    if message.get("action") == "AUTH":
                        auth_response = {
                            "id": message["id"],
                            "origin_action": "AUTH",
                            "result": {
                                "browser_id": device_id,
                                "user_id": user_id,
                                "user_agent": custom_headers['User-Agent'],
                                "timestamp": int(time.time()),
                                "device_type": "extension",
                                "version": "4.26.2",
                                "extension_id": "lkbnfiajjmbhnfledhphioinpickokdi"
                            }
                        }
                        logger.debug(auth_response)
                        await websocket.send(json.dumps(auth_response))
                    elif message.get("action") == "PONG":
                        pong_response = {"id": message["id"], "origin_action": "PONG"}
                        logger.debug(pong_response)
                        await websocket.send(json.dumps(pong_response))

            finally:
                send_ping_task.cancel()

    except Exception as e:
        logger.error(f"Error with proxy {proxy}: {str(e)}")
        return None

async def main():
    try:
        with open("user_id.txt", "r") as file:
            user_id = file.read().strip()
    except FileNotFoundError:
        logger.error("user_id.txt file not found. Exiting.")
        return

    logger.info(f"Using User ID: {user_id}")

    try:
        with open("local_proxies.txt", "r") as file:
            all_proxies = [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        logger.error("local_proxies.txt file not found. Exiting.")
        return

    if not all_proxies:
        logger.error("No proxies available. Exiting.")
        return

    active_proxies = random.sample(all_proxies, min(len(all_proxies), 100))
    tasks = {asyncio.create_task(connect_to_wss(proxy, user_id, random.choice(URILIST))): proxy for proxy in active_proxies}

    while True:
        done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task.result() is None:
                failed_proxy = tasks[task]
                logger.info(f"Removing failed proxy: {failed_proxy}")
                active_proxies.remove(failed_proxy)
                new_proxy = random.choice(all_proxies)
                active_proxies.append(new_proxy)
                tasks[asyncio.create_task(connect_to_wss(new_proxy, user_id, random.choice(URILIST)))] = new_proxy
            tasks.pop(task)

if __name__ == "__main__":
    asyncio.run(main())
