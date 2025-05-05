import asyncio
import os
import argparse
import json

from typing import List
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

from browser_use import Agent, Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig

from crawler import ShopCrawler

class ShopifyCrawler(ShopCrawler):
	""""Web crawler for Shopify websites based on Browser-Use (which in turn is based on Playwright)"""
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

	def create_checkout_task(self, website):
		"""Returns the prompt that is the responsible for navigating through checkout and filling in the correct information in checkout forms"""
		return f"""
		Navigate to checkout and fill in the all the form fields. The task is complete once all the information is accepted and the form has been submitted.
		
		# FROM CART OVERVIEW TO CART
		- Search for buttons to continue to checkout (search for options such as 'Process Order', 'Continue to payment')
		
		# PROCEED AS GUEST OR CREATE NEW ACCOUNT
		- If possible, try to proceed as guest (search for options such as 'Continue as guest', 'Order as guest', 'I am a new customer', 'Are you new here?' or 'New here?')
		- As a second resort, create a new account.
		- In any case, do not try to login to an existing account as this will not work

		# USER DATA
		Use the following profile for user data. Improvise data if there are other fields or the form does not submit.

		- Email address: {self.general['email_prefix']}+{website}@{self.general['email_suffix']}
		- Country: {self.profile['country']}
		- First Name: {self.general['first_name']}
		- Last Name: {self.general['last_name']}
		- ZIP Code: {self.profile['zip_code']}
		- City: {self.profile['city']}
		- Province: {self.profile['province']}
		- Phone Number: {self.profile['country_code']}{self.general['phone_number'][1:]}
		- Address: {self.profile['street']} {self.profile['house_number']}
		- ZIP Code: {self.profile['zip_code']}
		- City: {self.profile['city']}
		- Phone Number: {self.profile['country_code']}{self.general['phone_number'][1:]}

		# PAYMENT INFORMATION
		For payment options, choose credit card. Use the following information:
		- Card number: {self.general['credit_card_number']}
		- Expiry Date: {self.general['credit_card_expiry_month']}/{self.general['credit_card_expiry_year']}
		- Security Code: {self.general['credit_card_cvv']}
		- Name on card: {self.general['first_name']} {self.general['last_name']}

		# IMPORTANT RULES
		- Choose the standard delivery option.
		- Sometimes you have to click the dropdown menu first before you can see and select an option.
		- Do not click radio buttons more than once, since once click is enough for selection
		- The interactive elements from top layer of the current page inside the viewport shows many options for Expiry Date and Security Code fields, only interact with the ones that correspond to the index shown in the image.
		- Only click checkboxes related to 'terms and conditions'.
		- Ignore <button type='submit'>Continue /> in any language.
		- Ignore <select phone_country_select;Country/Region>
		- When you think that all the fields have been filled correctly, search for a submit button (search for options such as "Continue to Payment" or "Review Order"). This button should be visible in the image and at the bottom of the page.

		The task is complete if the form has been submitted. If the payment is processing or has failed, the task is still considered to be completed."""