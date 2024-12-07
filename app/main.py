import argparse
import platform
import aiohttp
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

class HttpError(Exception):
    pass


class ExchangeRateAPI:
    BASE_URL = "https://api.privatbank.ua/p24api/exchange_rates"
    @staticmethod
    async def fetch_exchange_rate(date: str, session: aiohttp.ClientSession) -> Dict[str, Any]:
        url = f"{ExchangeRateAPI.BASE_URL}?date={date}"
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                raise HttpError(f"Error status: {response.status} for {url}")
        except (aiohttp.ClientConnectorError, aiohttp.InvalidURL) as err:
            raise HttpError(f"Connection error for {url}: {str(err)}")

    @staticmethod
    async def fetch_all_rates(shift: int, currencies: List[str]) -> List[Dict[str, Dict]]:
        dates = [
            (datetime.now() - timedelta(days=i)).strftime("%d.%m.%Y")
            for i in range(shift)
        ]
        async with aiohttp.ClientSession() as session:
            tasks = [ExchangeRateAPI.fetch_exchange_rate(date, session) for date in dates]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for response in responses:
            if isinstance(response, Exception):
                print(f"Error fetching data: {response}")
            else:
                adapted_data = ExchangeRateAdapter.adapt(response, currencies)
                results.append(adapted_data)
        return results


class ExchangeRateAdapter:
    @staticmethod
    def adapt(data: Dict[str, Any], currencies: List[str]) -> Dict[str, Dict[str, Dict[str, float]]]:
        date = data.get("date")
        exchange_rates = data.get("exchangeRate", [])
        filtered_data = {
            rate["currency"]: {
                "sale": rate.get("saleRateNB") or rate.get("saleRate"),
                "purchase": rate.get("purchaseRateNB") or rate.get("purchaseRate"),
            }
            for rate in exchange_rates
            if rate.get("currency") in currencies
        }
        return {date: filtered_data}


class ArgumentHandler:
    def __init__(self):
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument(
            "shift",
            type=int,
            nargs="?",
            default=1,
            help="Зміщення не більше, ніж за останні 10 днів (1 = без зміщення)"
        )
        self.parser.add_argument(
            "add_currency_code",
            type=str,
            nargs="*",
            choices=[
                "AUD", "CAD", "CZK", "DKK", "HUF", "ILS", "JPY", "LVL", 
                "LTL", "NOK", "SKK", "SEK", "CHF", "GBP", "USD", "BYR", 
                "EUR", "GEL", "PLZ"
            ],
            help="Додаткові валюти в форматі кодів"
        )

    def parse(self) -> argparse.Namespace:
        return self.parser.parse_args()


async def main(args: argparse.Namespace):
    if not (0 <= args.shift <= 10):
        raise ValueError("Зміщення має бути у межах від 0 до 10")

    currencies = ["USD", "EUR"] + args.add_currency_code
    return await ExchangeRateAPI.fetch_all_rates(args.shift, currencies)


if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    arg_handler = ArgumentHandler()
    args = arg_handler.parse()

    try:
        results = asyncio.run(main(args))
        print(json.dumps(results, indent=4))
    except ValueError as e:
        print(f"Invalid input: {e}")
