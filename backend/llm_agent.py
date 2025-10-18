import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

class LLMAgent:
    def __init__(self):
        """
        Initialize LLM Agent with Groq (FREE API)
        """
        groq_api_key = os.getenv("GROQ_API_KEY")
        
        if not groq_api_key:
            raise ValueError(
                "GROQ_API_KEY not found in environment variables.\n"
            )
        
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.8,
            api_key=groq_api_key
        )
        print("LLM Agent initialized with Groq (Free API)")

    def generate_quote(self, temperature, humidity, pressure=None):
        """Generate literature-style quote based on sensor data"""
        
        temp_desc = "warm" if temperature > 25 else "cool" if temperature < 20 else "comfortable"
        humidity_desc = "humid" if humidity > 60 else "dry" if humidity < 40 else "balanced"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a poetic literary assistant that creates beautiful, 
            inspiring quotes based on environmental conditions. Your quotes should be:
            - Short (max 2 sentences, under 100 characters total)
            - Poetic and metaphorical
            - Related to the indoor environment
            - Uplifting and thought-provoking
            - In the style of famous authors or philosophers"""),
            ("user", """The room is {temp_desc} at {temperature}°C and {humidity_desc} 
            with {humidity}% humidity. Generate ONE beautiful quote that reflects 
            this atmosphere.""")
        ])
        
        try:
            chain = prompt | self.llm | StrOutputParser()
            
            quote = chain.invoke({
                "temperature": temperature,
                "humidity": humidity,
                "temp_desc": temp_desc,
                "humidity_desc": humidity_desc
            })

            return quote.strip().strip('"').strip("'")
        
        except Exception as e:
            print(f"Error generating quote: {e}")
            return "The environment whispers wisdom to those who listen."

    def summarize_emails(self, emails):
        """Summarize multiple emails into a concise message"""
        
        if not emails:
            return "No new emails at this time.", "low"
        
        email_list = []
        urgent_count = 0
        
        for email in emails[:5]:
            status = "URGENT" if email['is_important'] else ""
            email_list.append(
                f"{status} From: {email['sender'][:30]}\n"
                f"Subject: {email['subject'][:50]}\n"
                f"Preview: {email['snippet'][:80]}..."
            )
            if email['is_important']:
                urgent_count += 1
        
        email_text = "\n\n".join(email_list)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an email summarization assistant. Create a VERY concise 
            summary (max 150 characters) of the emails that:
            - Mentions the total number of emails
            - Highlights urgent ones if any
            - Lists key senders or topics
            - Is direct and actionable
            Keep it short for small display screens!"""),
            ("user", """Summarize these emails:\n\n{email_text}\n\n
            Total emails: {count}
            Urgent emails: {urgent}""")
        ])
        
        try:
            chain = prompt | self.llm | StrOutputParser()
            
            summary = chain.invoke({
                "email_text": email_text,
                "count": len(emails),
                "urgent": urgent_count
            })
            
            if urgent_count > 0:
                priority = "high"
            elif len(emails) > 3:
                priority = "medium"
            else:
                priority = "low"
            
            return summary.strip(), priority
        
        except Exception as e:
            print(f"Error summarizing emails: {e}")
            return f"{len(emails)} new emails", "low"

    def generate_combined_message(self, sensor_data, emails):
        """Generate a combined message with quote and email summary"""
        
        quote = self.generate_quote(
            sensor_data['temperature'],
            sensor_data['humidity'],
            sensor_data.get('pressure')
        )
        
        email_summary, priority = self.summarize_emails(emails)
        
        return {
            "quote": quote,
            "email_summary": email_summary,
            "priority": priority,
            "sensor_data": sensor_data,
            "email_count": len(emails),
            "timestamp": sensor_data.get('timestamp', '')
        }

if __name__ == "__main__":
    try:
        agent = LLMAgent()
        
        sensor_data = {
            "temperature": 28.5,
            "humidity": 65,
            "pressure": 1013,
            "timestamp": "2025-10-18 10:30:00"
        }
        
        print("\n--- Generating Quote ---")
        quote = agent.generate_quote(sensor_data['temperature'], sensor_data['humidity'])
        print(f"Quote: {quote}")
        
        mock_emails = [
            {
                "sender": "john@example.com",
                "subject": "Project Update",
                "snippet": "Hi, just wanted to update you on the project progress...",
                "is_important": False
            },
            {
                "sender": "boss@company.com",
                "subject": "URGENT: Meeting Tomorrow",
                "snippet": "Please confirm your attendance for tomorrow's meeting...",
                "is_important": True
            }
        ]
        
        print("\n--- Summarizing Emails ---")
        summary, priority = agent.summarize_emails(mock_emails)
        print(f"Summary: {summary}")
        print(f"Priority: {priority}")
        
        print("\n--- Combined Message ---")
        combined = agent.generate_combined_message(sensor_data, mock_emails)
        print(f"Quote: {combined['quote']}")
        print(f"Email: {combined['email_summary']}")
        print(f"Priority: {combined['priority']}")
        
    except ValueError as e:
        print(f"\n {e}")