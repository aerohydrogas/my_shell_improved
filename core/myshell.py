import asyncio
import json
import random
import secrets
import time

from better_proxy import Proxy
from hexbytes import HexBytes
from web3 import Web3
from web3.exceptions import TimeExhausted
from wonderwords import RandomSentence
from curl_cffi.requests import AsyncSession
from fake_useragent import UserAgent

from inputs.config import MOBILE_PROXY_CHANGE_IP_LINK, MOBILE_PROXY
from .utils import Web3Utils, logger


class MyShell:
    def __init__(self, key: str, proxy: str = None, rpc_url: str = 'https://opbnb-mainnet-rpc.bnbchain.org'):
        self.w3 = Web3Utils(http_provider=rpc_url, key=key)
        # self.proxy = Proxy.from_str(proxy.strip()).as_url if proxy else None

        headers = {
            'authority': 'api.myshell.ai',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en',
            'content-type': 'application/json',
            'myshell-client-version': 'v1.5.4',
            'myshell-service-name': 'organics-api',
            'origin': 'https://app.myshell.ai',
            'platform': 'web',
            'referer': 'https://app.myshell.ai/',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'timestamp': str(int(time.time() * 1000)),
            'user-agent': UserAgent().random
        }

        self.session = AsyncSession(
            headers=headers,
            # proxies={"http": self.proxy, "https": self.proxy},
            impersonate="chrome110",
            verify=False,
            trust_env=True
        )

        self.proxy = None
        self.visitor_id = MyShell.get_visitor_id()

    async def define_proxy(self, proxy: str):
        if MOBILE_PROXY:
            await MyShell.change_ip()
            proxy = MOBILE_PROXY

        if proxy is not None:
            proxy = Proxy.from_str(proxy.strip()).as_url
            self.session.proxies.update({"http": proxy, "https": proxy})

    @staticmethod
    async def change_ip():
        async with AsyncSession() as session:
            await session.get(MOBILE_PROXY_CHANGE_IP_LINK)

    async def login(self):
        # print((await self.session.get("http://httpbin.org/ip")).text)
        url = 'https://api.myshell.ai/auth/verifySignature'

        msg = await self.get_sign_msg()

        json_data = {
            'publicAddress': self.w3.acct.address,
            'signature': self.w3.get_signed_code(msg),
            'invitationCode': '',
            'botSharingCode': '',
            'visitorId': self.visitor_id,
        }

        headers = self.session.headers.copy()
        headers['myshell-service-name'] = ""
        headers['visitor-id'] = self.visitor_id

        response = await self.session.post(url, headers=headers, json=json_data)

        if auth_token := response.json().get("token"):
            self.upd_login_token(auth_token)

        return bool(auth_token)

    async def get_sign_msg(self):
        url = 'https://api.myshell.ai/auth/generateNonce'

        headers = self.session.headers.copy()
        headers['myshell-service-name'] = ""
        headers['visitor-id'] = self.visitor_id

        json_data = {
            'publicAddress': self.w3.acct.address,
        }

        response = await self.session.post(url, json=json_data, headers=headers)
        return response.json()["nonce"]

    def upd_login_token(self, token: str):
        self.session.headers["authorization"] = f"Bearer {token}"

    async def chat_transaction_and_claim(self):
        await self.chat_with_bot()
        await asyncio.sleep(3)
        transaction_success, transaction_hash = await self.send_transaction(gwei=0.000010009)
        if not transaction_success:
            transaction_success, transaction_hash = await self.send_transaction(gwei=0.000020009)
        if not transaction_success:
            logger.error("вообще не получилось сделать транзу")
        await asyncio.sleep(3)
        if transaction_success:
            await asyncio.sleep(5)
            await self.post_transaction_hash(transaction_hash)
            await asyncio.sleep(20)
        return await self.claim_all()

    async def chat_with_bot(self):
        bot_ids = ["864", "4976", "6958", "1700067629"]
        random.shuffle(bot_ids)

        for bot_id in bot_ids:
            text = RandomSentence().sentence()
            response = await self.send_bot_msg(bot_id, text)
            logger.info(f"Sent message to bot: {text} | Answer: {response[:10]}...")
            await asyncio.sleep(random.uniform(20, 40))

    async def send_bot_msg(self, bot_id: str, msg: str):
        json_data = {
            'botId': bot_id,
            'conversation_scenario': 3,
            'message': msg,
            'messageType': 1,
        }

        response = await self.session.post('https://api.myshell.ai/v1/bot/chat/send_message', json=json_data)

        if "MESSAGE_REPLY_SSE_ELEMENT_EVENT_NAME_USER_SENT_MESSAGE_REPLIED" in response.text:
            return json.loads(response.text.split("data: ")[-1])["message"]["text"]

    async def send_transaction(self, gwei):
        w3_opbnb = Web3(Web3.HTTPProvider('https://opbnb-mainnet-rpc.bnbchain.org'))
        estimation_transaction = {
            'from': self.w3.acct.address,
            'to': HexBytes(0x4f9ce7a71eb3795d7d38694fdb0d897dd055e26d),
            'nonce': w3_opbnb.eth.get_transaction_count(Web3.to_checksum_address(self.w3.acct.address)),
            'data': '0x0bf74764000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000076d797368656c6c00000000000000000000000000000000000000000000000000',
            'type': '0x2',
            'chainId': 204
        }
        estimated_gas = w3_opbnb.eth.estimate_gas(estimation_transaction)
        transaction = {
            'from': self.w3.acct.address,
            'to': HexBytes(0x4f9ce7a71eb3795d7d38694fdb0d897dd055e26d),
            'gas': estimated_gas,
            'maxFeePerGas': Web3.to_wei(gwei, "gwei"),
            'maxPriorityFeePerGas': Web3.to_wei(0.00001, "gwei"),
            'nonce': w3_opbnb.eth.get_transaction_count(self.w3.w3.to_checksum_address(self.w3.acct.address)),
            'data': '0x0bf74764000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000076d797368656c6c00000000000000000000000000000000000000000000000000',
            'type': '0x2',
            'chainId': 204
        }
        signed = self.w3.acct.sign_transaction(transaction)
        for _ in range(3):
            try:
                tx_hash = w3_opbnb.eth.send_raw_transaction(signed.rawTransaction)
                receipt = w3_opbnb.eth.wait_for_transaction_receipt(tx_hash, timeout=240)
                if receipt.status == 1:
                    logger.info(f"transaction done. Hash: {tx_hash.hex()}. Gwei = {gwei}")
                    return True, tx_hash.hex()
                else:
                    logger.error(f"транза зафелилась, hash: {tx_hash.hex()}. Gwei = {gwei}")
                    return False, tx_hash.hex()
            except TimeExhausted as te:
                logger.error(f"Ошибка при проверке транзакции: {te}. Попытка еще...")
        logger.error("Все попытки отправки транзакции завершились неудачно")
        return False

    async def post_transaction_hash(self, tx_hash: str):
        json_data = {
            'txHash': tx_hash,
        }

        response = await self.session.post('https://api.myshell.ai/v1/season/task/get_blockchain_tx_status', json=json_data)
        return response.json() == {}

    async def claim_all(self):
        url = 'https://api.myshell.ai/v1/season/task/claim_all'

        response = await self.session.post(url)
        return response.json() == {}

    async def claim(self, task_id: str):
        json_data = {
            'taskId': task_id,
        }

        response = await self.session.post('https://api.myshell.ai/v1/season/task/claim', json=json_data)
        return response.json() == {}

    def logout(self):
        self.session.close()

    @staticmethod
    def get_visitor_id():
        segment = secrets.token_hex(7)
        return (f'{segment}-{secrets.token_hex(7)}-{secrets.token_hex(4)}'
            f'-{random.randint(100000, 999999)}-{segment}')