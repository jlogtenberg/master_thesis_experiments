# Leveraging LLM-based autonomous web agents for measuring personal data exfiltration in checkout forms

In this repository, you can find all the files that we have used to run the crawls. Let us start with a breakdown of the folders and files:

- `crawl_data` contains the configurations are saved and where the crawl data will be saved during crawling.
- `.env` contains the API keys for the main model and the planner model.
- `crawler.py` contains the main code for the ShopCrawler, that is used to run the crawls on the Semrush list.
- `crawler_shopify.py` contains the code for the ShopifyCrawler, which inherits from the ShopCrawler, to run the crawls on the Aftership list with a modified prompt for the Checkout agent.
- `main.py` manages the command line interaction with the crawler and contains a number of flags.
- `system_prompt.txt` contains the system prompt that is attached to each request of the LLM
- `websites_language_aftership.csv` contains website-language pairs for all the websites in the Aftership list.
- `websites_language_semrush.csv` contains website-language pairs for all the websites in the Semrush list.

# Creating uv environment
Before we are able to run the code, we have to install some packages. To manage all the required packages, we use the Python package and project manager [uv](https://docs.astral.sh/uv/).

We first create a new uv environment in the main repository:

`uv venv`

We then activate the environment:

`.venv\Scripts\activate`

After that, we can install the version of Browser Use, that we used for our experiments:

`uv pip install browser-use==0.1.41`

# Setting up the API keys

Without valid API keys, we are not able to send requests to the LLMs. Go to [Google AI Studios](https://aistudio.google.com) and request an API key. At the time of writing, there a free daily limits, so there is no payment involved.

Paste the API keys for the main model and the planner model in the designated places in the .env file

`GEMINI_API_KEY = ""
GEMINI_API_KEY_PLANNER = ""`

# Flags

In `main.py` there are number of different flags.

## Required flags
- `-w <website>` or `f <file>` to provide the website or list of websites that should be crawled.
- `-l <language>`, with possible language options dutch german, french, spanish, italian and swedish, is provided when `-w` is provided to specify the language profile that should be used.
- `--path` specifies the path to where the configuration files are and where the crawl data should be saved.

## Optional flags
- `-r` records the crawl(s) and saves the recording as WEBM files.
- `-c` captures the requests and responses between Browser Use in a conversation folder.
- `-n` captures the network traffic during the crawl and saves the data in a HAR file.
- `-p` captures the performance of the agents and saves it to a performance file.
- `-a` enables all of the above optional flags.
- `-d` enables consent decline mode, as the default mode is consent accept mode.
- `-s` enables Shopify, which uses ShopifyCrawler instead of ShopCrawler that has a different checkout prompt.


# Running the crawls

To run the four separate crawls, we used the following four commands.

Semrush list with accept consent mode

`uv run main.py -a -f websites_language_semrush.csv --path crawl_data/semrush_accept`

Semrush list with decline consent mode

`uv run main.py -a -d -f websites_language_semrush.csv --path crawl_data/semrush_decline`

Aftership with accept consent mode

`uv run main.py -a -s -f websites_language_aftership.csv --path crawl_data/aftership_accept`

Aftership with decline consent mode

`uv run main.py -a -s -d -f websites_language_aftership.csv --path crawl_data/aftership_decline`
