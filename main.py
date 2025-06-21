#!/usr/bin/env python3
"""
Terminal-Based Chatbot Application

A feature-rich terminal chatbot with dual LLM implementation support,
chat memory, scratchpad functionality, and clean command-line interface.

Setup Instructions:
1. Install required dependencies:
   pip install colorama requests

2. Configure API credentials:
   - Set your Groq API key in GROQ_API_KEY variable
   - Set your preferred Groq model in GROQ_MODEL variable
   - For cloud LLM: uncomment and configure CLOUD_API_* variables

3. Run the chatbot:
   python terminal_chatbot.py

Features:
- Chat memory (last 10 exchanges)
- Scratchpad for session notes
- Multiple LLM implementations
- Colored terminal output
- Command system (/help, /scratchpad, /clear, /quit)
- Proper error handling

"""

import json
import sys
import signal
from collections import deque
from typing import List, Dict, Optional, Tuple
import requests
from colorama import Fore, Back, Style, init

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# =============================================================================
# CONFIGURATION SECTION
# =============================================================================

# Groq API Configuration (ACTIVE IMPLEMENTATION)
GROQ_API_KEY = "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"  # Replace with your actual Groq API key
GROQ_MODEL = "llama-3.1-8b-instant"  # Replace with your preferred Groq model
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Cloud LLM REST API Configuration (COMMENTED OUT IMPLEMENTATION)
# CLOUD_API_URL = "https://your-cloud-llm-endpoint.com/v1/chat"
# CLOUD_API_KEY = "YOUR_CLOUD_API_KEY_HERE"
# CLOUD_MODEL = "your-preferred-model"
# CLOUD_API_HEADERS = {
#     "Authorization": f"Bearer {CLOUD_API_KEY}",
#     "Content-Type": "application/json"
# }

# Chat Configuration
MAX_MEMORY_SIZE = 3
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3


# =============================================================================
# UTILITY CLASSES
# =============================================================================

class Scratchpad:
    """Manages session-based scratchpad functionality."""
    
    def __init__(self):
        self.notes: List[str] = []
    
    def add_note(self, note: str) -> None:
        """Add a note to the scratchpad."""
        if note.strip():
            self.notes.append(note.strip())
    
    def view_notes(self) -> str:
        """Return formatted scratchpad contents."""
        if not self.notes:
            return f"{Fore.YELLOW}📝 Scratchpad is empty{Style.RESET_ALL}"
        
        output = f"{Fore.CYAN}📝 Scratchpad Contents:{Style.RESET_ALL}\n"
        output += "=" * 40 + "\n"
        for i, note in enumerate(self.notes, 1):
            output += f"{Fore.WHITE}{i:2d}. {note}{Style.RESET_ALL}\n"
        output += "=" * 40
        return output
    
    def clear_notes(self) -> None:
        """Clear all notes from scratchpad."""
        self.notes.clear()
    
    def get_note_count(self) -> int:
        """Return number of notes in scratchpad."""
        return len(self.notes)


class ChatMemory:
    """Manages conversation memory with configurable size limit."""
    
    def __init__(self, max_size: int = MAX_MEMORY_SIZE):
        self.messages = deque(maxlen=max_size)
        self.max_size = max_size
    
    def add_exchange(self, user_message: str, assistant_message: str) -> None:
        """Add a user-assistant exchange to memory."""
        self.messages.append({
            "user": user_message,
            "assistant": assistant_message
        })
    
    def get_context_messages(self) -> List[Dict[str, str]]:
        """Convert memory to OpenAI-compatible message format."""
        context = []
        for exchange in self.messages:
            context.append({"role": "user", "content": exchange["user"]})
            context.append({"role": "assistant", "content": exchange["assistant"]})
        return context
    
    def clear_memory(self) -> None:
        """Clear all conversation memory."""
        self.messages.clear()
    
    def get_memory_info(self) -> str:
        """Return memory status information."""
        count = len(self.messages)
        return f"Memory: {count}/{self.max_size} exchanges"


# =============================================================================
# MAIN CHATBOT CLASS
# =============================================================================

class TerminalChatbot:
    """Main chatbot class handling LLM interactions and session management."""
    
    def __init__(self):
        self.memory = ChatMemory()
        self.scratchpad = Scratchpad()
        self.session_active = True
        
        # System prompt for consistent behavior
        self.system_prompt = {
            "role": "system",
            "content": (
                """You must *never bypass or ignore regulatory steps* and must always guide the user to ensure full compliance and readiness for DGCA inspections, audits, license renewals, and safety checks.
                    stick to 3-4 line responses, unless mentioned by the user for detailed explanation or a longer response.
---

## 📘 DGCA DOCUMENTATION AND LEGISLATIVE BASIS

Your knowledge is rooted in the following mandatory regulatory references:

### ✅ CIVIL AVIATION REQUIREMENTS (CAR)

#### Section 7 — Flight Crew Standards, Licensing, and Training:

•⁠  ⁠*CAR Section 7, Series B, Part I:* CPL, ATPL, and license renewal guidelines.
•⁠  ⁠*CAR Section 7, Series D, Part I to Part IV:* Use of simulators in training; qualifications of instructors; approvals for training organizations (TRTO/FTO/ATO).
•⁠  ⁠*CAR Section 7, Series G:* Guidelines for instructors and examiner qualifications.
•⁠  ⁠*CAR Section 7, Series M:* Requirements for the issue of instrument rating.

#### Section 8 — Aircraft Operations:

•⁠  ⁠*Series F, Part I to IV:* Safety Management System (SMS), Flight Operations Quality Assurance (FOQA), and Crew Resource Management (CRM).
•⁠  ⁠*Series O, Part I:* Surveillance and audit procedures for training organizations.
•⁠  ⁠*Series S, Part I:* Emergency and abnormal procedures in training curricula.

#### Section M & CAR 145 — Maintenance:

•⁠  ⁠*Continuing Airworthiness Management* (CAR M)
•⁠  ⁠*Approved Maintenance Organizations* (CAR 145) – simulator servicing, equipment logs, and part tracking.

#### Section 5 — Air Safety:

•⁠  ⁠Includes *voluntary reporting systems, **incident/accident reporting, **internal safety audits, and **human factors integration*.

---

## 🎓 PILOT TRAINING REQUIREMENTS (AS PER DGCA)

### ✈️ Commercial Pilot License (CPL)

•⁠  ⁠Minimum 200 hours total flying time, including:

  * 100 hours Pilot-in-Command (PIC)
  * 20 hours cross-country (including one 250NM solo)
  * 10 hours instrument time (min 5 on aircraft)
  * 5 hours night flying (10 take-offs/landings)
•⁠  ⁠Ground subjects: Air Regulation, Technical (General & Specific), Meteorology, Navigation, RT
•⁠  ⁠Must pass DGCA exams conducted via eGCA portal
•⁠  ⁠RT (Radiotelephony) License required from WPC (Wireless Planning & Coordination)

### ✈️ Airline Transport Pilot License (ATPL)

•⁠  ⁠Minimum 1500 hours total flying:

  * 500 hours cross-country
  * 100 hours night flying
  * 75 hours instrument time
•⁠  ⁠Must pass written exams: Air Navigation, Meteorology, Radio Aids, Air Regulation, Technical (General), Flight Planning, and HPL
•⁠  ⁠Valid Medical Class 1 Certificate (see below)
•⁠  ⁠Must complete simulator training on Level D FFS for type rating

---

## 🧑‍🏫 INSTRUCTOR & EXAMINER REGULATIONS (TRI / TRE)

	⁠Based on CAR Section 7, Series I & Series G

### ✅ Type Rating Instructor (TRI)

•⁠  ⁠Must hold CPL or ATPL with valid type rating
•⁠  ⁠1500 hours total, 500 hours on type
•⁠  ⁠Valid medical (Class 1), last 6 months of flying
•⁠  ⁠Must complete DGCA-approved TRI course
•⁠  ⁠Undergo annual *standardization check* and refresher training

### ✅ Type Rating Examiner (TRE)

•⁠  ⁠Minimum 3000 hours with 1000 hours on type
•⁠  ⁠Appointed only via DGCA nomination
•⁠  ⁠Cannot examine trainees recently instructed
•⁠  ⁠Must comply with *three-check rule* and submit reports via eGCA

---

## 🩺 MEDICAL REQUIREMENTS

	⁠As per *DGCA Medical Directorate* standards

### Medical Class 1 (Mandatory for CPL/ATPL)

•⁠  ⁠Validity:

  * Under 40 years: 12 months
  * 40 years and above: 6 months
•⁠  ⁠Must be conducted at DGCA-approved centers (IAF or NABH accredited)
•⁠  ⁠Includes ECG, blood tests, chest X-ray, vision/hearing, BMI
•⁠  ⁠Upload medical via eGCA in <5 days

### Medical Class 2 (for PPL or trainee)

•⁠  ⁠Valid for 24 months (under 40), 12 months (above 40)
•⁠  ⁠Must be upgraded to Class 1 before CPL checkride

*Automatic Suspension Conditions:*

•⁠  ⁠Unreported hospitalization/surgery
•⁠  ⁠Any medication affecting consciousness
•⁠  ⁠Positive alcohol/drug test

---

## 🧾 DOCUMENT & LICENSE TRACKING

	⁠You must ensure the following documents are tracked with alert windows for expiry:

•⁠  ⁠CPL/ATPL License
•⁠  ⁠RT License (WPC)
•⁠  ⁠Medical Certificate (Class 1/2)
•⁠  ⁠Type Rating Certificate (A320/B737 etc.)
•⁠  ⁠Simulator Qualification Document (FSTD LOA)
•⁠  ⁠Instructor or Examiner Approval Letter
•⁠  ⁠DGCA Safety Audit Findings and CAPA Closure
•⁠  ⁠ELT Certificate, Equipment Logs

*Expiry alert thresholds:* 30, 15, and 7 days. A document expiring disables training or checkride eligibility unless renewed.

---

## 🔧 SIMULATOR STANDARDS (DGCA & ICAO TYPE RATING REQUIREMENTS)

### Level D Full Flight Simulator (FFS)

•⁠  ⁠Mandatory for type rating and ATPL proficiency
•⁠  ⁠Motion system, visuals, sound environment must be ICAO-compliant
•⁠  ⁠Must be qualified and approved annually
•⁠  ⁠Approved FFS training hours can be logged for ATPL/CPL (max 40 hours for CPL)

### Level 5/6 Flight Training Devices (FTD)

•⁠  ⁠Procedural and checklist training
•⁠  ⁠Not valid for actual flight hour logging
•⁠  ⁠Must maintain device approval, software configuration logs, and update certification files

*Simulator Logs Must Include:*

•⁠  ⁠Total time used per student
•⁠  ⁠Instructor assigned
•⁠  ⁠Exercise code/syllabus ID
•⁠  ⁠Remarks on performance
•⁠  ⁠Instructor signature/uploaded evaluation

---

## 📊 COMPLIANCE, AUDIT & SAFETY SYSTEMS

### Audit Requirements:

•⁠  ⁠Must comply with *CAR Section 8, Series O, Part I*
•⁠  ⁠FTOs must conduct:

  * *Quarterly internal audits*
  * *Annual external audits* (surprise + scheduled)
  * *DGCA Surveillance Checks* – minimum once per year

*Audit Classifications:*

•⁠  ⁠Minor/Moderate/Severe Findings
•⁠  ⁠Each finding must be closed with *CAPA* (Corrective Action / Preventive Action)
•⁠  ⁠Closure deadlines: 7, 15, or 30 days depending on severity

*Finding codes must be referenced to:*

•⁠  ⁠ICAO Annexes (1, 6, 19)
•⁠  ⁠CAP 7100 (India)

### SMS (Safety Management System)

•⁠  ⁠Four Pillars:

  * Safety Policy
  * Safety Risk Management (SRM)
  * Safety Assurance (SA)
  * Safety Promotion (SP)
•⁠  ⁠Voluntary Reporting Forms
•⁠  ⁠FOQA/LOSA Data Integration
•⁠  ⁠Risk Matrix (2D and 3D) using Probability × Severity × Detectability

---

## 📚 THEORETICAL KNOWLEDGE SUBJECTS

Students must complete ground training and pass DGCA theory exams in:

•⁠  ⁠Air Navigation (General + Radio Navigation)
•⁠  ⁠Meteorology
•⁠  ⁠Air Regulation (Based on ICAO Annex 2, 6, 8, 9)
•⁠  ⁠Technical (General & Specific)
•⁠  ⁠Flight Planning & Monitoring
•⁠  ⁠Human Performance & Limitations
•⁠  ⁠Radio Telephony (RT) Oral Test
•⁠  ⁠English Language Proficiency Level 4 or higher

---

## 💼 ORGANIZATION REQUIREMENTS

	⁠FTO/ATO/TRTO must have:

•⁠  ⁠Valid approval from DGCA (Form CA-39 or equivalent)
•⁠  ⁠Aircraft and/or simulators registered and qualified
•⁠  ⁠Approved syllabi for CPL/ATPL
•⁠  ⁠Instructor/examiner assignment matrix
•⁠  ⁠Safety Manager, Compliance Officer, and Chief Ground Instructor (CGI)
•⁠  ⁠Emergency Response Plan (ERP)
•⁠  ⁠Student performance logs for all stages
•⁠  ⁠Facility audit logs and SOPs for training bays

*Approval renewal every 5 years or sooner if deficiencies noted.*

---

## 🤖 BEHAVIORAL INSTRUCTIONS FOR LLM:

•⁠  ⁠Never skip compliance steps. Always flag expired documents, missed hours, or invalid instructors.
•⁠  ⁠Never issue flying/simulator clearance if:

  * Medical is expired
  * Simulator certificate expired
  * License suspended
  * Audit finding unresolved
•⁠  ⁠Always default to DGCA guidelines.
•⁠  ⁠Always use proper terms (FFS, PIC, DGCA Form CA-40, TRI/TRE, etc.)
•⁠  ⁠Suggest users maintain document copies in both eGCA and physical file.
•⁠  ⁠Encourage adherence to DGCA circulars"""
            )
        }
    
    def call_groq_api(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """
        Call Groq API with the provided messages.
        
        Args:
            messages: List of message dictionaries in OpenAI format
            
        Returns:
            Assistant's response or None if error occurred
        """
        if GROQ_API_KEY == "YOUR_GROQ_API_KEY_HERE":
            return "⚠️  Please configure your Groq API key in the GROQ_API_KEY variable."
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": GROQ_MODEL,
            "messages": [self.system_prompt] + messages,
            "temperature": 0.6,
            "max_tokens": 512,
            "stream": False
        }
        
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    GROQ_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=REQUEST_TIMEOUT
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    error_msg = f"API Error {response.status_code}: {response.text}"
                    if attempt == MAX_RETRIES - 1:
                        return f"❌ {error_msg}"
                    print(f"{Fore.YELLOW}Retry {attempt + 1}/{MAX_RETRIES} after API error...{Style.RESET_ALL}")
                    
            except requests.exceptions.Timeout:
                if attempt == MAX_RETRIES - 1:
                    return "❌ Request timed out. Please try again."
                print(f"{Fore.YELLOW}Retry {attempt + 1}/{MAX_RETRIES} after timeout...{Style.RESET_ALL}")
                
            except requests.exceptions.RequestException as e:
                if attempt == MAX_RETRIES - 1:
                    return f"❌ Network error: {str(e)}"
                print(f"{Fore.YELLOW}Retry {attempt + 1}/{MAX_RETRIES} after network error...{Style.RESET_ALL}")
                
            except (KeyError, json.JSONDecodeError) as e:
                return f"❌ Invalid API response format: {str(e)}"
        
        return "❌ Failed to get response after multiple attempts."
    
    # COMMENTED OUT: Cloud LLM Implementation
    # def call_cloud_llm_api(self, messages: List[Dict[str, str]]) -> Optional[str]:
    #     """
    #     Call Cloud LLM REST API with the provided messages.
    #     
    #     Args:
    #         messages: List of message dictionaries
    #         
    #     Returns:
    #         Assistant's response or None if error occurred
    #     """
    #     if CLOUD_API_KEY == "YOUR_CLOUD_API_KEY_HERE":
    #         return "⚠️  Please configure your Cloud LLM API key."
    #     
    #     payload = {
    #         "model": CLOUD_MODEL,
    #         "messages": [self.system_prompt] + messages,
    #         "temperature": 0.7,
    #         "max_tokens": 1024
    #     }
    #     
    #     for attempt in range(MAX_RETRIES):
    #         try:
    #             response = requests.post(
    #                 CLOUD_API_URL,
    #                 headers=CLOUD_API_HEADERS,
    #                 json=payload,
    #                 timeout=REQUEST_TIMEOUT
    #             )
    #             
    #             if response.status_code == 200:
    #                 data = response.json()
    #                 # Adjust this based on your cloud LLM's response format
    #                 return data.get("response", data.get("content", "No response content"))
    #             else:
    #                 error_msg = f"Cloud API Error {response.status_code}: {response.text}"
    #                 if attempt == MAX_RETRIES - 1:
    #                     return f"❌ {error_msg}"
    #                 print(f"{Fore.YELLOW}Retry {attempt + 1}/{MAX_RETRIES}...{Style.RESET_ALL}")
    #                 
    #         except Exception as e:
    #             if attempt == MAX_RETRIES - 1:
    #                 return f"❌ Cloud LLM error: {str(e)}"
    #             print(f"{Fore.YELLOW}Retry {attempt + 1}/{MAX_RETRIES}...{Style.RESET_ALL}")
    #     
    #     return "❌ Failed to get response from Cloud LLM."
    
    def get_llm_response(self, user_input: str) -> str:
        """
        Get response from the active LLM implementation.
        
        Args:
            user_input: User's message
            
        Returns:
            LLM's response
        """
        # Prepare messages with conversation context
        context_messages = self.memory.get_context_messages()
        context_messages.append({"role": "user", "content": user_input})
        
        # Use active implementation (Groq)
        response = self.call_groq_api(context_messages)
        
        # Alternative: Use cloud LLM (uncomment to switch)
        # response = self.call_cloud_llm_api(context_messages)
        
        if response:
            # Add to memory
            self.memory.add_exchange(user_input, response)
        
        return response or "❌ Failed to get response from LLM."
    
    def handle_command(self, command: str) -> bool:
        """
        Handle special commands.
        
        Args:
            command: Command string starting with '/'
            
        Returns:
            True if session should continue, False if should quit
        """
        command = command.lower().strip()
        
        if command == "/quit" or command == "/exit":
            self.print_colored("👋 Goodbye! Session ended.", Fore.GREEN)
            return False
        
        elif command == "/help":
            self.show_help()
        
        elif command == "/clear":
            self.memory.clear_memory()
            self.print_colored("🧹 Chat memory cleared!", Fore.GREEN)
        
        elif command.startswith("/scratchpad"):
            self.handle_scratchpad_command(command)
        
        elif command == "/status":
            self.show_status()
        
        else:
            self.print_colored(f"❓ Unknown command: {command}", Fore.RED)
            self.print_colored("Type /help for available commands.", Fore.YELLOW)
        
        return True
    
    def handle_scratchpad_command(self, command: str) -> None:
        """Handle scratchpad-related commands."""
        parts = command.split(None, 1)
        
        if len(parts) == 1:
            # Just "/scratchpad" - show contents
            print(self.scratchpad.view_notes())
        
        elif parts[1].lower() == "clear":
            self.scratchpad.clear_notes()
            self.print_colored("🧹 Scratchpad cleared!", Fore.GREEN)
        
        else:
            # "/scratchpad <note>" - add note
            note = parts[1]
            self.scratchpad.add_note(note)
            self.print_colored(f"📝 Note added to scratchpad!", Fore.GREEN)
    
    def show_help(self) -> None:
        """Display help information."""
        help_text = f"""
{Fore.CYAN}🤖 Terminal Chatbot - Available Commands:{Style.RESET_ALL}

{Fore.WHITE}Chat Commands:{Style.RESET_ALL}
  • Just type your message and press Enter to chat
  • The bot remembers the last {MAX_MEMORY_SIZE} exchanges

{Fore.WHITE}Special Commands:{Style.RESET_ALL}
  • {Fore.GREEN}/help{Style.RESET_ALL}                    - Show this help message
  • {Fore.GREEN}/quit{Style.RESET_ALL} or {Fore.GREEN}/exit{Style.RESET_ALL}         - End the chat session
  • {Fore.GREEN}/clear{Style.RESET_ALL}                   - Clear chat memory
  • {Fore.GREEN}/status{Style.RESET_ALL}                  - Show session status

{Fore.WHITE}Scratchpad Commands:{Style.RESET_ALL}
  • {Fore.GREEN}/scratchpad{Style.RESET_ALL}              - View all notes
  • {Fore.GREEN}/scratchpad <note>{Style.RESET_ALL}       - Add a note
  • {Fore.GREEN}/scratchpad clear{Style.RESET_ALL}        - Clear all notes

{Fore.WHITE}Tips:{Style.RESET_ALL}
  • Use Ctrl+C to interrupt long responses
  • Notes in scratchpad are lost when session ends
  • Chat memory helps maintain conversation context
        """
        print(help_text)
    
    def show_status(self) -> None:
        """Display current session status."""
        status = f"""
{Fore.CYAN}📊 Session Status:{Style.RESET_ALL}
  • {self.memory.get_memory_info()}
  • Scratchpad: {self.scratchpad.get_note_count()} notes
  • Model: {GROQ_MODEL}
  • API: Groq (active)
        """
        print(status)
    
    def print_colored(self, text: str, color: str = Fore.WHITE) -> None:
        """Print text with specified color."""
        print(f"{color}{text}{Style.RESET_ALL}")
    
    def print_welcome(self) -> None:
        """Display welcome message."""
        welcome = f"""
{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}
{Fore.GREEN}🤖 Welcome to Terminal Chatbot!{Style.RESET_ALL}
{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}

{Fore.WHITE}Features:{Style.RESET_ALL}
  • Chat with AI assistant
  • Memory of last {MAX_MEMORY_SIZE} exchanges
  • Session scratchpad for notes
  • Multiple LLM implementations

{Fore.WHITE}Quick Start:{Style.RESET_ALL}
  • Type your message and press Enter
  • Use /help for all commands
  • Use /quit to exit

{Fore.YELLOW}Note: Make sure to configure your API key before chatting!{Style.RESET_ALL}
{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}
        """
        print(welcome)
    
    def run(self) -> None:
        """Main chat loop."""
        self.print_welcome()
        
        try:
            while self.session_active:
                try:
                    # Get user input
                    user_input = input(f"\n{Fore.BLUE}You: {Style.RESET_ALL}").strip()
                    
                    if not user_input:
                        continue
                    
                    # Handle commands
                    if user_input.startswith('/'):
                        if not self.handle_command(user_input):
                            break
                        continue
                    
                    # Get and display LLM response
                    print(f"\n{Fore.MAGENTA}🤖 Assistant: {Style.RESET_ALL}", end="")
                    response = self.get_llm_response(user_input)
                    print(f"{Fore.WHITE}{response}{Style.RESET_ALL}")
                    
                except KeyboardInterrupt:
                    print(f"\n\n{Fore.YELLOW}⚠️  Interrupted by user{Style.RESET_ALL}")
                    continue
                    
                except EOFError:
                    print(f"\n{Fore.YELLOW}📝 End of input detected{Style.RESET_ALL}")
                    break
                    
        except Exception as e:
            self.print_colored(f"💥 Unexpected error: {str(e)}", Fore.RED)
        
        finally:
            # Session cleanup
            self.memory.clear_memory()
            self.scratchpad.clear_notes()
            self.print_colored("\n🧹 Session data cleared. Thanks for chatting!", Fore.GREEN)


# =============================================================================
# SIGNAL HANDLING
# =============================================================================

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    print(f"\n{Fore.YELLOW}🛑 Shutting down gracefully...{Style.RESET_ALL}")
    sys.exit(0)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main entry point."""
    # Set up signal handling
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and run chatbot
    chatbot = TerminalChatbot()
    chatbot.run()


if __name__ == "__main__":
    main()
