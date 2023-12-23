import os
import random
import aiohttp
import asyncio
import aiofiles

from itertools import cycle
from typing import Optional, List, Dict, Any

from aiohttp import ClientError 
from asyncio import TimeoutError

class NitroGen:
    BASE_URL: str = "https://api.discord.gx.games/v1/direct-fulfillment"
    PARTNER_PROMOTIONS_URL: str = "https://discord.com/billing/partner-promotions/1180231712274387115/"
    PROXY_SCRAPER_URL: str = "https://api.proxyscrape.com/?request=getproxies&proxytype=http&timeout=2000&country=all&ssl=all&anonymity=all"
    
    def __init__(self, **kwargs: Optional[Any]) -> None:
        self.session = None
        self.proxy_list = []
        self.proxy_list_iter = None

        self.code_generation_target = kwargs.get("code_generation_target", int(input("How many codes would you like to generate?: ")))
        self.use_proxies = kwargs.get("use_proxies", input("[Not necessary] Use proxies? (y/n): ").lower() == "y")
        self.test_proxy_url = kwargs.get("test_proxy_url", "https://www.google.com/")
        self.output_path = kwargs.get("output_path", "./nitro_urls.txt")
        self.proxies_input_path = kwargs.get("proxies_path", None)
        self.test_proxies = kwargs.get("test_proxies", True)
        self.max_workers = kwargs.get("max_workers", 100)
        timeouts = kwargs.get("timeouts", {})
        self.timeouts = {
            "get_token": aiohttp.ClientTimeout(total=timeouts.get("get_token", 5)),
            "test_proxy": aiohttp.ClientTimeout(total=timeouts.get("test_proxy", 5))
        }

    async def get_http_proxies(self, session: aiohttp.ClientSession) -> List:
        async with session.get(self.PROXY_SCRAPER_URL) as req:
            if req.status == 200:
                return [proxy.strip() for proxy in (await req.text()).split("\n") if proxy]
        return []

    async def get_payload(self) -> Dict:
        return {"partnerUserId": "".join(random.choice("0123456789abcdef") for _ in range(64))}

    async def get_token(self, session: aiohttp.ClientSession) -> Optional[str]:
        proxy = None
        formatted_proxy = None
        payload = await self.get_payload()

        if (self.use_proxies) and (not self.proxy_list):
            raise Exception("Ran out of working proxies!")

        if self.use_proxies:
            proxy = next(self.proxy_list_iter)
            formatted_proxy = f"http://{proxy}"

        try:
            async with session.post(self.BASE_URL, json=payload, proxy=formatted_proxy, timeout=self.timeouts.get("get_token")) as response:
                return await response.json(content_type=None)
        except (ClientError, TimeoutError):
            if (self.proxy_list) and (proxy in self.proxy_list):
                self.proxy_list.remove(proxy)
                self.proxy_list_iter = cycle(self.proxy_list)
                print(f"Removed {proxy}.")
            else:
                print("Something went wrong with POST request...")
        except Exception as e:
            print(e.__class__, e)
            print(proxy)

    async def test_proxy(self, session: aiohttp.ClientSession, proxy: str) -> Optional[str]:
        try:
            formatted_proxy = f"http://{proxy}"
            async with session.get(self.test_proxy_url, proxy=formatted_proxy, timeout=self.timeouts.get("test_proxy")) as response:
                if response.status == 200:
                    print(f"Proxy {proxy} is working.")
                    return proxy
                else:
                    print(f"Proxy {proxy} returned a non-200 status code: {response.status}")
        except (ClientError, TimeoutError):
            pass
        except Exception as e:
            print(e.__class__, e)
            print(proxy)

    async def test_all_proxies(self, session: aiohttp.ClientSession, proxies: List) -> List:
        tasks = [self.test_proxy(session, proxy) for proxy in proxies]
        results = await asyncio.gather(*tasks)
        return [proxy for proxy in results if proxy]

    async def main(self) -> None:
        generated_codes = 0

        async with aiohttp.ClientSession() as session:
            if self.use_proxies:
                if (self.proxies_input_path) and (os.path.exists(self.proxies_input_path)):
                    async with aiofiles.open(self.proxies_input_path, "r", encoding="utf-8") as f:
                        self.proxy_list = [proxy.strip() for proxy in (await f.read()).split("\n")]
                else:
                    print("No proxies found in working_directory, if you would like to use your own proxies please create a \"proxies.txt\" file!\nFetching from proxyscrape api...")
                    self.proxy_list = await self.get_http_proxies(session) # NSA proxies

                if self.test_proxies:
                    print(f"Testing proxies against {self.test_proxy_url}...")
                    self.proxy_list = await self.test_all_proxies(session, self.proxy_list)

                if not self.proxy_list:
                    raise Exception("No working proxies! (failed to scrape or passed bad proxies)")
                
                self.proxy_list_iter = cycle(self.proxy_list)
            
            print("Starting nitro generator...")

            while generated_codes < self.code_generation_target:
                generation_target = self.max_workers
                if (self.code_generation_target - generated_codes) < self.max_workers:
                    generation_target = (self.code_generation_target - generated_codes)

                tasks = [self.get_token(session) for _ in range(generation_target)]
                responses = await asyncio.gather(*tasks)
                working_codes = []

                for response in responses:
                    if generated_codes >= self.code_generation_target:
                        break
                    
                    if not response:
                        continue
                    
                    working_codes.append(self.PARTNER_PROMOTIONS_URL + response.get("token"))
                    generated_codes += 1

                print(f"Generated ({generated_codes}/{self.code_generation_target}) total codes - ({len(working_codes)}/{len(tasks)}) workers returned tokens...")

                if not working_codes:
                    raise Exception("No workers returned codes! (ratelimited?)")

                async with aiofiles.open(self.output_path, "a", encoding="utf-8") as f:
                    await f.write("\n".join(working_codes) + "\n")
            
            print(f"Saved {self.code_generation_target} nitro urls to {self.output_path}...")

if __name__ == "__main__":
    asyncio.run(NitroGen().main())
