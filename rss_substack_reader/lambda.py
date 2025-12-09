import os
import json
import boto3
from datetime import datetime
from html import unescape
from bs4 import BeautifulSoup
import requests

def lambda_handler(event, context):
    """
    Weekly Lambda function to:
    1. Fetch latest 5 posts from Substack RSS
    2. Clean HTML content from posts
    3. Send to Claude Sonnet 4.5 via OpenRouter
    4. Store response in DynamoDB
    """
    
    # Environment variables
    RSS_FEED_URL = os.environ['RSS_FEED_URL']
    OPENROUTER_API_KEY = os.environ['OPENROUTER_API_KEY']
    DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE_NAME']
    TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
    
    # Initialize DynamoDB client
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)

    # Initialize SNS client
    sns = boto3.client('sns')
    
    try:
        # Step 1: Fetch and parse RSS feed
        response = requests.get(RSS_FEED_URL)

        rss_feed = response.text
        soup = BeautifulSoup(rss_feed, features="html.parser")
        entries = soup.find_all('item')

        if len(entries) < 1:
            raise Exception("No entries found in RSS feed")
        
        # Step 2: Extract and clean the latest 5 posts
        print("Processing posts...")
        posts_data = process_rss_posts(entries, 5)
                
        # Step 3: Create prompt for Claude
        prompt = create_analysis_prompt(posts_data)
        
        # Step 4: Call OpenRouter with Claude Sonnet 4.5
        print("Calling OpenRouter API...")
        response_html = call_openrouter(prompt, OPENROUTER_API_KEY)
        
        # Step 5: Store in DynamoDB
        print("Writing to DynamoDB...")
        record_key = datetime.now().strftime('%Y%m%d')
        
        table.put_item(
            Item={
                'date_key': record_key,
                'timestamp': datetime.now().isoformat(),
                'response_html': response_html,
            }
        )

        # Step 6: Send email with results via SNS
        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject="Substack Meta Essay",
            Message=response_html
        )
        
        print(f"Successfully stored record with key: {record_key}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Success',
                'record_key': record_key,
                'posts_processed': len(posts_data)
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

def process_rss_posts(posts_list, limit):
    """
    Process a list of posts from an RSS feed - parsed by beautifulsoup4.
    It enforces a limit of posts to be parsed.
    
    :param posts_list: List of posts
    :param limit: Limit of posts to parse
    """
    # Running list of processed posts
    _posts_data = list()

    for entry in posts_list[:limit]:
        # Extract content from content:encoded field
        # This is a direct tag in the XML, not a dictionary
        content_encoded_tag = entry.find('content:encoded')
        
        if content_encoded_tag:
            # Get the text content (which includes HTML/CDATA)
            content_encoded = content_encoded_tag.get_text()
            
            # Decode HTML entities
            decoded_content = unescape(content_encoded)
            
            # Parse HTML and extract clean text
            content_soup = BeautifulSoup(decoded_content, 'html.parser')
            clean_text = content_soup.get_text(separator='\n', strip=True)
        else:
            clean_text = ""
        
        # Extract other fields from XML tags
        title = entry.find('title').get_text() if entry.find('title') else 'Untitled'
        link = entry.find('link').get_text() if entry.find('link') else ''
        published = entry.find('pubDate').get_text() if entry.find('pubDate') else ''
        
        print(f"Title: {title}")
        print(f"Content preview: {clean_text[:200]}...")
        print("-" * 80)
        
        _posts_data.append({
            'title': title,
            'link': link,
            'published': published,
            'content': clean_text
        })

        return _posts_data


def create_analysis_prompt(posts_data):
    """
    Create a prompt for Claude that includes all 5 posts.
    This is a boilerplate prompt - customize as needed.
    """
    prompt = """
    I will provide you below the encoded text content for the Substack posts i have released this week.

"""
    
    for i, post in enumerate(posts_data, 1):
        prompt += f"""
POST {i}: {post['title']}

Content:
{post['content']}

---

"""
    
    prompt += """
# Instructions
Your goal is to generate 1 new essay that pulls together the ideas of those 5 posts to create a meta essay that ties those posts together.

The opening section must be at max 2 paragraphs and use a short story to a) hook the reader and b) naturally present and illustrate the theme of this essay and c) the story must be a relatable day to day example. This opening section must be formatted so it captures the user's attention to read the rest of the essay. Please bear in mind the opening section must be illustrative of that meta-idea in discussion for this new post, not the other original 5 posts.

The writing should be clear (the 5th grade level benchmark through use of simpler words and day to day examples) but retain its complex subjects. Titles must be written in sentence case.

Critical style requirements:

Do not include the typical sentence construction by LLMs like ChatGPT where it makes forced contrasting affirmations, such as "This isn't just X... - it's Y". Also minimize the usage of em dashes.

Do not use the constructs you always default to, such as "here's what most people get wrong" and "but a lot of people miss this". I do not want the text to include excessively hyperbolized statements nor obviously contrasting sentence construction.

Minimize references back to the opening story throughout the essay. Use the opening story to establish context, then shift to direct principles and insights. The story is a launching point, not a recurring anchor.

Be concise and direct. Each section should make its point efficiently without repetitive examples or over-explanation. If an idea can be conveyed in two sentences instead of five, use two.

Avoid redundancy. Don't restate the same concept multiple times with different examples unless each example adds genuinely new insight.

Target a 4-5 minute read (approximately 1,000-1,200 words). This is shorter than typical because it prioritizes clarity and impact over comprehensiveness.

Format the resulting text in regular markdown syntax, ready to send as an email body.
"""
    
    return prompt


def call_openrouter(prompt, api_key):
    """
    Call OpenRouter API to access Claude Sonnet 4.5
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aws.lambda.eu-west-2.rss-substack-reader",
    }
    
    payload = {
        "model": "anthropic/claude-sonnet-4.5",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 4096  # Adjust as needed
    }
    
    response = requests.post(url, json=payload, headers=headers, timeout=300)
    response.raise_for_status()
    
    result = response.json()
    return result['choices'][0]['message']['content']