import asyncio
import os
import argparse
import json
import base64

from typing import List
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

from datetime import datetime
from browser_use import Agent, Browser, BrowserConfig, Controller
from browser_use.browser.context import BrowserContext, BrowserContextConfig

class ShopCrawler:
	""""Web crawler for shopping websites based on Browser-Use (which in turn is based on Playwright)"""

	def __init__(
		self,
		websites_language_pairs: List[tuple],
		record: False,
		capture_conversation: False,
		capture_network: False,
		capture_performance: False,
		cookies: True,
		path: str
	):
		self.base_path = path
		self.data_path = f"{self.base_path}/data"

		self.websites_language_pairs = websites_language_pairs

		self.data = self.load_data(f"{self.base_path}/user_data.json")
		self.general = self.data['general']
		self.system_prompt = self.get_system_prompt()

		agent, planner = self.connect_to_llm()
		self.agent = agent
		self.planner = planner

		self.task2 = self.create_product_selection_task()
		self.tasks = [None, self.task2, None]

		self.agents_config = self.load_data(f"{self.base_path}/agent_config.json")

		self.record = record
		self.capture_conversation = capture_conversation
		self.capture_network = capture_network
		self.capture_performance = capture_performance
		self.cookies = cookies

	def load_data(self, file_path):
		"""Load data from the JSON file."""
		with open(file_path, 'r') as file:
			return json.load(file)

	def initialize_llm(self, api_key) -> ChatGoogleGenerativeAI:
		"""Initializes Gemini 2.0 using the API key"""
		return ChatGoogleGenerativeAI(
			model='gemini-2.5-flash-preview-04-17', 
			api_key=SecretStr(api_key),
			temperature=0.0
		)

	def initialize_planner(self, api_key) -> ChatGoogleGenerativeAI:
		return ChatGoogleGenerativeAI(
			model='gemini-2.0-flash', 
			api_key=SecretStr(api_key),
			temperature=0.0
		)

	def get_system_prompt(self):
		"""Return the system prompt from the hard-coded path"""
		with open('system_prompt.txt', 'r', encoding='utf-8') as file:
			return file.read()

	def connect_to_llm(self):
		"""Connects to the agent and planner LLMs, using the API keys in the .env file"""
		# Loading in the api keys from .env
		load_dotenv()
		api_key_agent = os.getenv('GEMINI_API_KEY')
		api_key_planner = os.getenv('GEMINI_API_KEY_PLANNER')

		# Initilization of the agent and planner
		agent = self.initialize_llm(api_key_agent)
		planner = self.initialize_planner(api_key_planner)

		return agent, planner

	async def run_crawl(self) -> None:
		"""Initializes the browser and runs the crawl on the website(s)"""
		agent_names = list(self.agents_config.keys())

		for website, language in self.websites_language_pairs:
			browser = self.initialize_browser()
			context = self.initialize_context(website)

			self.language = language

			# Choose the corresponding profile for the language
			self.profile = self.data["profile"].get(language, {})

			# Configure the navigation and cookie step to the correct website
			self.tasks[0] = self.create_entry_task(website)
			self.tasks[2] = self.create_checkout_task(website)

			# Main loop that creates the browser and runs the agent
			async with await browser.new_context(config = context) as context:
				print(f"Starting agent on {website} with language profile {language}")
				for i, task in enumerate(self.tasks):
					crawl_start = datetime.utcnow().isoformat()
					history = await self.run_agent(website, context, task, agent_names[i])
					crawl_end = datetime.utcnow().isoformat()

					if history.is_done():
						if self.record:
							await self.save_screenshot(context, website, agent_names[i])
						if self.capture_performance:
							model_outputs = history.model_outputs()
							self.save_model_outputs(website, history, agent_names[i])

					# Update the performance details of the agent, if enabled
					if self.capture_performance:
						self.update_performance(website, history, agent_names[i], crawl_start, crawl_end)
						
					# Stop the crawl of the website, if one of the agents fails
					if not history.is_successful():
						break
				await context.close_current_tab()
			await browser.close()

	async def run_agent(self, website, context, task, agent_name):
		"""Initializes and runs the agent with the given task on the current browser context"""

		# Get the agent configuration
		agent_config = self.agents_config.get(agent_name)

		# Check if the agent exists and if a planner is required and adjust values accordingly
		if agent_config and agent_config['planner']:
			planner_llm = self.planner
			planner_interval = agent_config['planner_interval']
		else:
			planner_llm = None
			planner_interval = 0

		controller = self.get_controller()

		# Create the conversation path (or not), based on whether it is enabled
		save_conversation_path = (f"{self.data_path}/{website}/conversation/{agent_name}/" if self.capture_conversation else None)

		# Initialize agent with set configuration
		agent = Agent(
			browser_context = context,
			task = task,
			llm = self.agent,
			controller = controller,
			planner_llm = planner_llm,
			planner_interval = planner_interval,
			max_actions_per_step = agent_config['max_actions_per_step'],
			use_vision = True,
			use_vision_for_planner = True,
			save_conversation_path = save_conversation_path,
			override_system_message = self.system_prompt
		)
	
		# Run the agent
		history = await agent.run(max_steps = agent_config['max_steps'])
		return history

	def initialize_browser(self):
		"""Initializes the browser"""
		return Browser(config = BrowserConfig(
				headless=False,
				disable_security=True,
			)
		)

	def initialize_context(self, website):
		"""Initializes the browser context"""
		save_recording_path = f'{self.data_path}/{website}/' if self.record else None
		save_har_path = f'{self.data_path}/{website}/traffic.har' if self.capture_network else None

		return BrowserContextConfig(
			minimum_wait_page_load_time=3.0,
			user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.106 Safari/537.36',
			highlight_elements=True,
			save_recording_path = save_recording_path,
			save_har_path = save_har_path,
			viewport_expansion=-1
		)

	async def save_screenshot(self, context, website, agent):
		"""Takes and saves screenshot after task completion"""
		screenshot_dir = f"{self.data_path}/{website}/screenshots/"
		os.makedirs(screenshot_dir, exist_ok=True)

		screenshot_path = f"{screenshot_dir}{agent}.png"
		screenshot_b64 = await context.take_screenshot()
		screenshot_bytes = base64.b64decode(screenshot_b64)
		
		with open(screenshot_path, "wb") as f:
			f.write(screenshot_bytes)

	def save_model_outputs(self, website, history, agent):
		raw_actions = history.model_actions()
		model_outputs = history.model_outputs()

		# Structures the raw actions performed by the model
		structured_actions = [
			{"action": {"done": {"text": a["done"]["text"], "success": a["done"]["success"]}}}
			if "done" in a else {"action": {k: v}}
			for a in raw_actions
			for k, v in a.items() if k != "interacted_element"
		]

		# Combines the structured actions with the response of the model
		combined_output = []
		action_index = 0

		for output in model_outputs:
			state = {
				"evaluation_previous_goal": output.current_state.evaluation_previous_goal,
				"memory": output.current_state.memory,
				"next_goal": output.current_state.next_goal
			}

			num_actions = len(output.action)
			step_actions = [
				structured_actions[action_index + i]["action"]
				for i in range(num_actions)
				if action_index + i < len(structured_actions)
			]
			action_index += num_actions

			combined_output.append({
				"current_state": state,
				"actions": step_actions
			})

		file_path = f"{self.data_path}/{website}/model_outputs.json"

		# Writes response of the model with actions to file
		if os.path.exists(file_path):
			with open(file_path, 'r') as f:
				existing_data = json.load(f)
		else:
			existing_data = {}

		existing_data[agent] = combined_output

		os.makedirs(os.path.dirname(file_path), exist_ok=True)
		with open(file_path, "w", encoding="utf-8") as f:
			json.dump(existing_data, f, ensure_ascii=False, indent=2)

	
	def update_performance(self, website, history, agent, crawl_start, crawl_end):
		"""Updates the performance of the crawler for a website"""

		# Create an empty entry for the performance data
		performance = {}

		# Open the performance JSON file
		if os.path.exists(f"{self.data_path}/performance.json"):
			with open(f"{self.data_path}/performance.json", "r", encoding="utf-8") as f:
				try:
					performance = json.load(f)
				except json.JSONDecodeError:
					performance = {}

		# Check whether there is an entry for the website already in the JSON file
		if website not in performance:
			performance[website] = {}

		# Determine the status of the agent of the crawler by history
		status = 'success' if history.is_successful() else 'failure'

		# Create a new entry for the current agent with the performance data
		performance[website][agent] = {
			"status": status,
			"steps_taken": history.number_of_steps(),
			"duration": history.total_duration_seconds(),
			"start_time": crawl_start,
			"end_time": crawl_end,
			"input_tokens": history.total_input_tokens(),
			"final_result": history.final_result()
		}

		# Write the data to the JSON file
		with open(f"{self.data_path}/performance.json", "w", encoding="utf-8") as f:
			json.dump(performance, f, indent=4, ensure_ascii=False)

	def get_controller(self):
		"""Initializes and returns a controller, that excludes specific actions for the agent"""
		controller = Controller(exclude_actions=['search_google'])
		return controller

	def create_entry_task(self, website):
		"""Returns the prompt that is responsible for the navigation to the given website, the accepting or declining of cookies and the closing of pop-ups upon loading the website"""
		accept_prompt =  f"""
		Go to {website}, accept cookies, wait for a moment and close any other pop-ups. If there is no obvious cookie dialogue upon loading the website, do not scroll down to look for it.
		
		# NOTES
		- The additional pop-ups can usually be closed by clicking on the 'X' or options such as 'Close'.
		- When asked for multiple versions of the webshop, choose the {self.language.capitalize()} webshop

		The task is complete once there is no cookie dialogue or pop-up."""

		decline_prompt =  f"""
		Go to {website}, decline cookies, wait for a moment and close any other pop-ups. If there is no obvious cookie dialogue upon loading the website, do not go looking for one.

		# DECLINE INSTRUCTIONS
		- Proritize searching for options such as 'Decline, 'Refuse' or 'Only necessary cookies'.
		- Only if there no option straightforward to decline the cookies, search for options such as 'Prefences', 'Manage preferences', 'Manage cookies' or 'Personalise cookies'. Choose to reject or decline cookies in the submenu and safe preferences or selection if required (search for options such as 'Save preferences' or 'Save selection').
		
		# NOTES
		- The additional pop-ups can usually be closed by clicking on the 'X' or options such as 'Close'.
		- When asked for multiple versions of the webshop, choose the option that stays on the current webshop

		The task is complete once there is no cookie dialogue or pop-up."""

		return accept_prompt if self.cookies else decline_prompt

	def create_product_selection_task(self):
		"""Returns the prompt that is responsible for finding and adding a product to the cart"""
		return f"""
		Find and add a product to cart on the current website.
		
		# SEARCHING A PRODUCT
		- Go to the product page of one of the products.

		# ADDING A PRODUCT TO THE CART
		- Do not favourite or add a product to the wishlist, but add the product to cart.
		- Adding a product to the cart may require choosing a specific colour or size first (represented as buttons or a dropdown menu). Always choose an option that is in stock.
		- When a product is out of stock, return to the product overview page and choose another product to add to the cart.
		
		# GO TO CART OVERVIEW
		- Once the product has been added to the cart, on most websites, one can go to the cart overview by clicking on the icon on the top right of the page, or by clicking the checkout button.
		- Search for options such as 'Go to shopping cart' after product has been added to the cart.
		
		The task is complete once the cart overview is shown and a product is in the cart."""

	def create_checkout_task(self, website):
		"""Returns the prompt that is the responsible for navigating through checkout and filling in the correct information in checkout forms"""
		return f"""
		Navigate to checkout and fill in the all the form fields. The task is complete once all the information is accepted and the form has been submitted.
		
		# FROM CART OVERVIEW TO CHECKOUT
		- Search for buttons to continue to checkout (search for options such as 'Process Order', 'Continue to payment')
		
		# PROCEED AS GUEST OR CREATE NEW ACCOUNT
		- If possible, try to proceed as guest (search for options such as 'Continue as guest', 'Order as guest', 'I am a new customer', 'Are you new here?' or 'New here?')
		- As a second resort, create a new account.
		- In any case, do not try to login to an existing account as this will not work

		# USER DATA
		Use the following profile for user data. Improvise data if there are other fields or the form does not submit.

		- Gender: {self.general['gender']} (verify that the option has been selected in the image and do not click the option if it has been selected in the image)
		- First Name: {self.general['first_name']}
		- Last Name: {self.general['last_name']}
		- Email address: {self.general['email_prefix']}+{website}@{self.general['email_suffix']}
		- Password: {self.general['password']}
		- Country Code: {self.profile['country_code']}
		- Phone Number: {self.profile['local_format']}
		- Country Code + Phone Number: {self.profile['international_format']}
		- Date of birth: {self.general['date_of_birth']} (use the format the website requires, typing in the date might required entering day, month and year one by one)

		- Street: {self.profile['street']}
		- House Number: {self.profile['house_number']}
		- Address: {self.profile['street']} {self.profile['house_number']}
		- ZIP Code: {self.profile['zip_code']}
		- City: {self.profile['city']}
		- Province: {self.profile['province']}
		- Country: {self.profile['country']}

		# PAYMENT INFORMATION
		For payment options, choose {self.profile['payment_options']}. For credit card, use the following information:
		- Card number: {self.general['credit_card_number']}
		- Expiry Month: {self.general['credit_card_expiry_month']}
		- Expiry Year: {self.general['credit_card_expiry_year']}
		- CVV: {self.general['credit_card_cvv']}
		- Card Holder: {self.general['first_name']} {self.general['last_name']}

		# IMPORTANT RULES
		- Choose the standard delivery option.
		- Sometimes you have to click the dropdown menu first before you can see and select an option.
		- Do not click radio buttons more than once, since once click is enough for selection
		- If you combine the country code and phone number, do not write the first 0 of the phone number.
		- Not all of the provided user data is required in every form, you do not have to look for all of them to submit the form
		- In some cases credit card fields only appear once you click on the "Continue to Payment" button, scrolling down more does not help
		- When you think that all the fields have been filled correctly, search for a continue button (search for options such as "Continue" or "Continue to payment")

		The task is complete if the form has been submitted. If the payment is processing or has failed, the task is still considered to be completed."""