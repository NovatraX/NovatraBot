import os
import random
from datetime import datetime, timedelta, timezone
from groq import Groq

class AccountabilityHelpers:
    def __init__(self):
        api_key = os.getenv("API_KEY")
        self.aiclient = Groq(api_key=api_key) if api_key else None
        
    def generate_motivation(self, tasks):
        """Generate a motivational message based on the user's tasks."""
        if not tasks:
            return "Keep going strong! Every step counts."
            
        formatted_tasks = "\n".join(f"- {t}" for t in tasks)
        motivation_prompt = f"User has logged the following tasks today:\n{formatted_tasks}\n\nProvide a single-line, powerful motivational message based on these tasks."
        
        try:
            if self.aiclient:
                response = self.aiclient.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": "You reply in single sentence as small as possible. You are a highly motivational and insightful assistant. You speak in English and use simple terms so that all people can understand it. Your role is to analyze a user's logged tasks and provide them with a single-line, impactful message that fuels their determination, boosts their morale, and encourages them to keep going. Make it personal, inspiring, and energizing. Keep it concise but powerful!",
                        },
                        {"role": "user", "content": motivation_prompt},
                    ],
                    temperature=0.8,
                    max_tokens=50,
                    top_p=1,
                )
                return response.choices[0].message.content.strip()
        except Exception:
            pass
            
        
        fallback_messages = [
            "Every task completed brings you closer to your goals!",
            "Your consistency is building something amazing!",
            "Small steps today, giant leaps tomorrow!",
            "Your dedication is truly inspiring!",
            "Keep pushing forward, you're doing great!",
        ]
        return random.choice(fallback_messages)
        
    def calculate_streak(self, last_logged, today):
        """Calculate a user's streak based on their last logged date.
        Implements a streak system."""
        if not last_logged:
            return 0
            
        days_difference = (today - last_logged).days
        
        
        if days_difference == 1:
            return 1            
        
        else:
            return -1  
        
    def calculate_streak_bonus(self, streak):
        """Calculate bonus multipliers based on streak milestones."""
        if streak >= 100:
            return 3.0  
        elif streak >= 30:
            return 2.0  
        elif streak >= 7:
            return 1.5  
        else:
            return 1.0  
        
    def calculate_novacoins_bonus(self, streak):
        """Calculate the NovaCoins bonus based on streak with progressive scaling."""
        
        base_bonus = 10
        
        
        if streak % 100 == 0:  
            base_bonus += 100
        elif streak % 30 == 0:  
            base_bonus += 50
        elif streak % 7 == 0:  
            base_bonus += 20
            
        
        scaling_bonus = int(base_bonus * (0.03 * streak))
        
        return max(base_bonus, scaling_bonus)
        
    def get_random_bonus(self, min_val=1, max_val=5, streak=1):
        """Generate a random NovaCoins bonus that scales with streak."""
        
        if streak >= 30:
            min_val += 4
            max_val += 10
        elif streak >= 7:
            min_val += 2
            max_val += 5
            
        return random.randint(min_val, max_val)
        
    def get_today(self):
        """Get today's date in UTC timezone."""
        return datetime.now(timezone.utc).date()
        
    def get_current_timestamp(self):
        """Get the current timestamp in UTC timezone."""
        return int(datetime.now(timezone.utc).timestamp())
        
    def calculate_task_reward(self, task_length, task_count, streak):
        """Calculate reward for a task based on its complexity and user's current stats."""
        
        base_reward = 5
        
        
        length_factor = min(len(task_length) / 20, 3)  
        
        
        diminishing_factor = max(1.0 - ((task_count - 1) * 0.05), 0.5)  
        
        
        streak_factor = self.calculate_streak_bonus(streak)
        
        final_reward = base_reward * length_factor * diminishing_factor * streak_factor
        
        
        randomness = random.uniform(0.9, 1.1)
        
        return int(final_reward * randomness)