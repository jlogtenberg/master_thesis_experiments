import asyncio
import os
import argparse
import json
import csv

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr
from crawler import ShopCrawler
from crawler_shopify import ShopifyCrawler

def parse_arguments():
	"""Parses the command line arguments"""
	parser = argparse.ArgumentParser(description="Provide a single website or a list from a file.")

	parser.add_argument("-w", "--website", help="Specify a single website.")
	parser.add_argument("-f", "--file", help="Specify a file containing a list of websites.")
	parser.add_argument("-l", "--language", choices=["dutch", "german", "french", "spanish", "italian", "swedish"], help="Specify a language (Dutch, German, French, Spanish, Italian, Swedish).")
	parser.add_argument("-d", dest="cookies", action="store_false", help="Do not accept cookies (decline them instead).")
	parser.add_argument("-r", "--record", action="store_true", default=False, help="Enables recording of the crawl session.")
	parser.add_argument("-c", "--capture_conversations", action="store_true", default=False, help="Enables capturing agent conversations for each step.")
	parser.add_argument("-n", "--capture_network", action="store_true", default=False, help="Enables capturing and storing a HAR file of the network traffic.")
	parser.add_argument("-p", "--capture_performance", action="store_true", default=False, help="Enables capturing of performance details for each task of the agent")
	parser.add_argument("-s", "--shopify", action="store_true", default=False, help="Use ShopifyCrawler instead of ShopCrawler.")
	parser.add_argument("-a", "--all", action="store_true", default=False, help="Enables all flags (-r, -c, -n, -p).")
	parser.add_argument("--path", help="Specify a folder name with the config files and where the data should be saved.")

	args = parser.parse_args()

	# Check whether flag -a and any of flags -r, -c, -n or -p are enabled at the same time
	if args.all and (args.record or args.capture_conversations or args.capture_network or args.capture_performance):
		print("Error: The -a (all) flag cannot be used together with individual flags (-r, -c, -n, -p).")
		exit(1)

	# Set flags -r, -c, -n or -p to true if flag -a is enabled
	if args.all:
		args.record = True
		args.capture_conversations = True
		args.capture_network = True
		args.capture_performance = True

	# Check if both flag -w and -f are provided at the same time
	if args.website and args.file:
		print("Error: You cannot provide both a website (-w) and a file (-f) at the same time.")
		exit(1)

	# Check whether -l and -w are enabled at the same time and otherwise create one (website,language) pair
	if args.website:
		if not args.language:
			print("Error: Language (-l) must be specified when using a single website (-w).")
			exit(1)
		website_language_pairs = [(args.website, args.language)]

	# Check whether -l and -f are are enabled at the same time and otherwise create (website,language) pairs
	elif args.file:
		if args.language:
			print("Error: The -l (language) flag cannot be used together with a file (-f).")
			exit(1)
		try:
			website_language_pairs = []
			with open(args.file, mode="r", newline='', encoding='utf-8') as csvfile:
				reader = csv.DictReader(csvfile, delimiter=';')
				for row in reader:
					website = row.get("website")
					language = row.get("language")
					if not website or not language:
						print(f"Error: Missing website or language in row: {row}")
						exit(1)
					if language not in ["dutch", "german", "french", "spanish", "italian", "swedish"]:
						print(f"Error: Invalid language '{language}' in row: {row}")
						exit(1)
					website_language_pairs.append((website.strip(), language.strip()))
		except FileNotFoundError:
			print(f"Error: File '{args.file}' not found.")
			exit(1)
		except Exception as e:
			print(f"Error reading file: {e}")
			exit(1)

	else:
		print("Error: Please provide a website (-w) or a file (-f).")
		exit(1)

	return website_language_pairs, args.record, args.capture_conversations, args.capture_network, args.capture_performance, args.shopify, args.cookies, args.path

async def main():
	# Get all the relevant parameters for the crawler from the command line and hand them to the crawler
	websites_language_pairs, record, capture_conversation, capture_network, capture_performance, use_shopify, cookies, path = parse_arguments()

	CrawlerClass = ShopifyCrawler if use_shopify else ShopCrawler
	crawler = CrawlerClass(
		websites_language_pairs = websites_language_pairs,
		record = record,
		capture_conversation = capture_conversation,
		capture_network = capture_network,
		capture_performance = capture_performance,
		cookies = cookies,
		path = path
	)

	# Run the crawler with the set configuration
	await crawler.run_crawl()

if __name__ == "__main__":
	asyncio.run(main())