import pywhatkit, threading, datetime, pyjokes, os, time, arrow, re, bs4, requests, vlc, queue, warnings, smtplib, random, sys, wikipedia, webbrowser
from pygame import mixer
from turtle import *
from tkinter import messagebox, simpledialog
from random import choice, randint
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import turtle as t
import tkinter as tk
from time import sleep
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
from copy import deepcopy
import subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

VOICE_PATH = os.path.expanduser("~/.piper-voices/en_US-amy-medium.onnx")

def _piper(text: str):
    cmd = f"echo '{text}' | piper-tts --model {VOICE_PATH} --output_raw | aplay -r 22050 -f S16_LE -t raw"
    subprocess.run(cmd, shell=True, capture_output=True)

def _clean(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]*`", "", text)
    text = re.sub(r"https?://\S+", "", text)
    return " ".join(text.split()).strip()

def talk1(text: str):
    """Female voice."""
    print(f"Marin: {text}")
    threading.Thread(target=_piper, args=(_clean(text),), daemon=True).start()

def talk2(text: str):
    """Male voice."""
    print(f"Marin: {text}")
    threading.Thread(target=_piper, args=(_clean(text),), daemon=True).start()

# Create a single global engine and queue for thread-safe TTS
tts_queue = queue.Queue()
engine = None
engine_lock = threading.Lock()
warnings.filterwarnings("ignore", category=UserWarning)
def timer(inp):
    #inp = input("Set your timer: ").lower()
    # Get positions of keywords
    pos1 = inp.find('timer for')
    pos2 = inp.find('hour') # -1 if last inp is "timer for X hours"
    pos3 = inp.find('minutes') # -1 if last inp is "timer for X hour Y minutes" "timer for Y minutes"
    # user only set hours
    if pos3 == -1:
        addmin = 0
        addhour = inp[pos1 + len('timer for'):pos2]
    # if user only set minutes
    elif pos2 == -1:
        addhour = 0
        addmin = inp[pos1 + len('timer for'):pos3] 
    # user set both hours and minutes
    else:
        addhour = inp[pos1 + len("timer for"):pos2]
        addmin = inp[pos2 + len("hour"):pos3] 
    # Get the current time
    current_hour = arrow.now().format('H')
    current_min = arrow.now().format('m')
    current_sec = arrow.now().format('s')
    # Calculate the target time
    new_hour = int(current_hour) + int(addhour)
    new_min = int(current_min) + int(addmin)
    new_sec = int(current_sec)
    # Adjust for overflow of minutes and hours
    if new_min >= 60:
        new_min -= 60
        new_hour += 1
    new_hour = new_hour % 24
    end_time = str(new_hour) + ':' + str(new_min) + ':' + str(new_sec)
    talk1(f"Timer set for {addhour} hour(s) and {addmin} minute(s). It will go off at {end_time}.")
    # Wait for the timer to finish
    while True:
        current_time = arrow.now().format('H:m:s')
        if current_time == end_time:
            talk2("Time's up!")
            #import os
            #os.system('start alarm.wav')
            from pygame import mixer
            mixer.init()
            mixer.music.load('alarm.wav')
            mixer.music.play()
            while mixer.music.get_busy():  # wait until playback finishes
                time.sleep(1)
            time.sleep(1)
            break
warnings.filterwarnings("ignore", category=UserWarning)
def alarm_instructions():
    # Tell you the format to set the timer
    return ('''set your alarm clock\nyou can use the format of:
    -"tset an alarm for 7 a.m., or"
    -"set an alarm for 2:15 p.m."''')
def know_all(inp):
    apikey = "4EQ3U6QQ49"
    url = f"http://api.wolframalpha.com/v1/result?appid={apikey}&i={requests.utils.quote(inp)}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            talk1(f"Answer: {response.text}")
            return response.text
        else:
            talk1(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"WolframAlpha error: {e}")
        talk2(f"WolframAlpha error: {e}")
        try:
            ans = wikipedia.summary(inp, sentences=5)  # Fixed typo: sentences not sentencces
            talk2(ans)
            return ans
        except Exception as e:
            print(f"Wikipedia error: {e}")
            talk1("I'm still learning. I don't know your answer yet")
            return None
def alarm(inp):
    #Set the alarm
    #inp = input("What time?\n>>>").lower()
    p1 = inp.find("alarm for") # alarm for 3:30 p.m.
    p2 = inp.find("a.m.")
    p3 = inp.find("p.m.")
    p4 = inp.find(":")
    #Handle the four different case
    if p2 != -1 and p4 != -1:
        inp = inp[p1+len("alarm for")+1:p2] + "AM"
    elif p3 != -1 and p4 != -1:
        inp = inp[p1 + len("alarm for") + 1:p3] + "PM"
    elif p2 != -1 and p4 != -1:
        inp = inp[p1 + len("alarm for") + 1:p2] + ":00 AM"
    elif p3 != -1 and p4 != -1:
        inp = inp[p1 + len("alarm for") + 1:p3] + ":00 PM"
        
    talk2(f"Ok! your alarm will go off at {inp}!")
    while True:
        #Obtain time and change it to  7:25 AM format
        tm = arrow.now().format('h:mm A')
        time.sleep(5)
        if inp.strip()==tm.strip():
            talk1("Your alarm has gone Off!!")
            mixer.init()
            mixer.music.load("alarm.wav")
            mixer.music.play()
            while mixer.music.get_busy():  # wait until playback finishes
                time.sleep(1)
            break
        time.sleep(5)


'''
def email():
    emails = {
    'shafiq': '2208018@student.ruet.ac.bd',
    'selim': '2208015@student.ruet.ac.bd',
    'preta': '2208036@student.ruet.ac.bd',
    'mohammad': '2208008@student.ruet.ac.bd',
    'apurbo': '2208027@student.ruet.ac.bd'
    }
    # Credentials (better: use environment variables)
    sender = "pythonlusty@gmail.com"
    password = "ypsazczivgabqsyd"  # fallback for demo

    # Ask for recipient
    talk1("Whom do you want to send the mail?")
    while True:
        receiver = take_command()
        if receiver in emails:
            break
        else:
            talk2("Sorry, I don’t recognize that name. Try again.")
            talk1("Enter his/her name")
            name = input("Enter name:")
            receiver = name
            if name in emails:
                break
            else:
                talk2("What is his/her roll number??\n:>>>")
                roll=input("What is his/her roll number??\n:>>>")
                if '@gmail.com' in roll:
                    emails[name]=roll
                    #receiver = roll
                    break
                elif '@student.ruet.ac.bd' not in roll:
                    emails[name]=f'{roll}@student.ruet.ac.bd'
                    #receiver = roll
                    break
    talk1(f"Sending mail to {receiver} ({emails[receiver]})")
    talk2("Which mode u want to write mail?\nsay 1 for speech\nsay 2 for writing")
    mode = input("Which mode u want to write mail?\nwrite 1 for speech\n2 for writing\n>>")
    if mode =='1':
        subject = auto_sub()
        body = auto_body()
    else:
        talk1("Enter subject")
        subject = input("Enter subject\n>>>")
        talk1("Enter body")
        body = input("Enter body\n>>")
    # Combine into email format
    message = f"Subject: {subject}\n\n{body}"

    # Send email
    import pyautogui
    pyautogui.alert(
        f"Reciever:{receiver}\nEmail:{emails[receiver]}\nSubject:{subject}\nBody text:\n{body}",title="Sending emails review"
    )
    talk1("Are you sure to send the mail(yes/no)??\n>>>")
    ask = input("Are you sure to send the mail(yes/no)??\n>>>")
    if ask=='no':
        import sys
        sys.exit()
    else:
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, emails[receiver], message)
            server.quit()
            talk1("Email sent successfully!")
            print("Email sent successfully!")
        except Exception as e:
            talk2(f"Failed to send email. Error: {e}")
            print(f"Failed to send email. Error: {e}")'''

def email():
    emails = {
        'shafiq': '2208018@student.ruet.ac.bd',
        'selim': '2208015@student.ruet.ac.bd',
        'preta': '2208036@student.ruet.ac.bd',
        'mohammad': '2208008@student.ruet.ac.bd',
        'apurbo': '2208027@student.ruet.ac.bd'
    }

    sender = "pythonlusty@gmail.com"
    password = os.getenv("EMAIL_PASSWORD", "ypsazczivgabqsyd")  # safer fallback

    # Ask for recipient
    talk1("Whom do you want to send the mail?")
    while True:
        receiver = take_command()
        if receiver in emails:
            recipient_email = emails[receiver]
            break
        else:
            talk2("Sorry, I don’t recognize that name. Try again.")
            name = input("Enter name: ").lower().strip()
            if name in emails:
                receiver = name
                recipient_email = emails[name]
                break
            else:
                roll = input("Enter roll number or full email: ").strip()
                if '@' in roll:
                    recipient_email = roll
                else:
                    recipient_email = f"{roll}@student.ruet.ac.bd"
                emails[name] = recipient_email
                receiver = name
                break

    talk1(f"Sending mail to {receiver} ({recipient_email})")

    # Mode selection
    mode = input("Choose mode (1=speech, 2=writing): ").strip()
    if mode not in ('1', '2'):
        mode = '2'
    subject = input("Enter subject: ")
    body = input("Enter body: ")

    # Review
    root = tk.Tk()
    root.withdraw()
    import tkinter.messagebox as mb
    mb.showinfo("Email Review", f"To: {receiver}\nEmail: {recipient_email}\nSubject: {subject}\nBody:\n{body}")
    ask = input("Are you sure you want to send the mail (yes/no)? ").lower().strip()
    if ask != 'yes':
        talk2("Email cancelled.")
        return  # don’t kill the whole assistant

    # Send email
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipient_email, f"Subject: {subject}\n\n{body}")
        server.quit()
        talk1("Email sent successfully!")
        print("Email sent successfully!")
    except Exception as e:
        talk2(f"Failed to send email. Error: {e}")
        print(f"Failed to send email. Error: {e}")


def news():
    url = 'https://www.nbcnews.com/nightly-news-full-episodes'
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"Error {e} occurred while fetching the webpage.")
        talk2(f"Error {e} occurred while fetching the webpage.")
        return
    soup = bs4.BeautifulSoup(res.text, 'html.parser')
    # Look for .mp4 links in the page source
    links = re.findall(r'https://[^"\s]+\.mp4', res.text)
    if not links:
        print("No video links found.")
        talk1("No video links found.")
        return
    # Play the first valid link
    video_url = links[0]
    print(f"Playing video: {video_url}")
    player = vlc.MediaPlayer(video_url)
    player.play()
    try:
        input("Press Enter to stop playback...")
    finally:
        player.stop()
def talk1(text):
    """Female voice"""
    tts_queue.put((1, text))

def talk2(text):
    """Male voice"""
    tts_queue.put((0, text))


class GuessTheWordGame:
    def __init__(self):
        """Initialize the Guess the Word game"""
        # Word list
        self.words = [
            "nice","want","have","need","wish","give","take","love","care","help",
            "hold","keep","know","send","make","find","feel","look","show","move",
            "live","stay","join","play","work","read","talk","hear","plan","hope",
            "deal","lead","grow","rise","fall","meet","save","open","shut","turn",
            "stop","wait","walk","jump","rest","pick","push","pull","pack","pass",
            "sign","test","call","cook","bake","wash","boil","flip","stir","pour",
            "peel","feed","lift","sort","draw","type","edit","sing","snap","film",
            "zoom","chat","mail","link","code","load","sync","view","copy","clip",
            "text","post","roll","spin","calm","kind","fair","good","fine","pure",
            "true","easy","fast","slow","soft","hard","busy","cool","warm","mild",
            "bold","cute","neat","sure","okay","able","just","even","else","only",
            "some","many","more","less","most","ever","once","then","when","soon",
            "later","here","away","down","back","over","into","onto","from","with",
            "amid","upon","near","side","area","line","part","item","unit","word",
            "gate","door","room","hall","yard","park","lake","tree","rock","road",
            "path","hill","farm","ship","boat","crew","port","zone","city","town",
            "site","shop","bank","mall","home","desk","seat","lamp","wire","pipe",
            "wall","roof","tile","belt","ring","tool","card","note","form","file",
            "data","info","page","user","name","like","tell","warn"
        ]
        
        # Setup screen
        self.screen = t.Screen()
        self.screen.bgcolor("lavender")
        self.screen.setup(600, 500)
        t.hideturtle()
        t.tracer(False)
        t.up()
        
        # Create drawing turtle
        self.drawer = t.Turtle()
        self.drawer.hideturtle()
        self.drawer.up()
        
        # Game state
        self.word = ""
        self.score = 6
        self.missed = []
        self.right = []
        self.circles = []
        self.title_thread = None
        self.running = True
    
    def update_title(self):
        """Update title with time and hints"""
        while self.running:
            current_time = arrow.now().format('h:mm A')
            hint1 = random.choice(self.words)
            hint2 = random.choice(self.words)
            t.title(f"Guess the Word Game   |   {current_time}  |  Hint1: {hint1}    |   Hint2: {hint2}")
            time.sleep(1)
    
    def show_intro(self):
        """Display introduction messages"""
        messages = [
            ("Welcome to the Guess the Word Game!", ("Arial", 20, "bold"), 2),
            ("Try to guess the 4-letter word!", ("Arial", 16, "normal"), 2),
            ("You have 6 attempts. Good luck!", ("Arial", 16, "normal"), 2)
        ]
        
        for msg, font, delay in messages:
            t.goto(-270, 200)
            t.write(msg, font=font)
            t.update()
            time.sleep(delay)
            t.clear()
    
    def draw_blanks(self):
        """Draw blank lines for each letter"""
        for i in range(len(self.word)):
            self.drawer.goto(-270 + 150 * i, -200)
            self.drawer.pendown()
            self.drawer.forward(100)
            self.drawer.penup()
        t.update()
    
    def create_circles(self):
        """Create attempt indicator circles"""
        for i in range(6):
            c = t.Turtle("circle")
            c.shapesize(3)
            c.color("black", "sky blue")
            c.up()
            c.goto(-150 + 50 * i, 0)
            self.circles.append(c)
        t.update()
    
    def update_score_display(self):
        """Update the score display"""
        t.goto(-270, 200)
        t.write(f"Attempts left: {self.score}", font=("Arial", 16, "normal"))
        t.update()
    
    def update_missed_display(self):
        """Update the incorrect guesses display"""
        t.goto(-270, 150)
        t.clear()
        t.write("Incorrect guesses: " + ", ".join(self.missed), font=("Arial", 16, "normal"))
        t.update()
    
    def draw_letter(self, letter, position):
        """Draw a correctly guessed letter"""
        self.drawer.goto(-270 + 150 * position, -200)
        self.drawer.write(letter.upper(), font=("Arial", 48, "bold"))
        t.update()
    
    def check_win(self):
        """Check if all letters have been guessed"""
        return all(letter in self.right for letter in self.word)
    
    def handle_correct_guess(self, inp_word):
        """Handle a correct letter guess"""
        self.right.append(inp_word)
        for i in range(len(self.word)):
            if self.word[i] == inp_word:
                self.draw_letter(inp_word, i)
        
        if self.check_win():
            self.running = False
            messagebox.showinfo("Congratulations!", f"You guessed the word '{self.word.upper()}' correctly!")
            return True
        return False
    
    def handle_incorrect_guess(self, inp_word):
        """Handle an incorrect letter guess"""
        self.missed.append(inp_word)
        self.score -= 1
        self.update_missed_display()
        
        # Hide one circle
        self.circles[-(6 - self.score)].hideturtle()
        self.update_score_display()
        
        if self.score == 0:
            self.running = False
            messagebox.showinfo("Game Over", f"You've run out of attempts! The word was '{self.word.upper()}'.")
            return True
        return False
    
    def get_user_input(self):
        """Get and validate user input"""
        while True:
            inp_word = t.textinput("Guess the Word", "Enter a letter:")
            
            if inp_word is None:
                return None
            
            inp_word = inp_word.lower()
            
            # Validate input
            if len(inp_word) != 1 or not inp_word.isalpha():
                messagebox.showwarning("Warning", "Please enter a single letter.")
                continue
            
            if inp_word in self.missed or inp_word in self.right:
                messagebox.showwarning("Already Guessed", "You already guessed that letter!")
                continue
            
            return inp_word
    
    def game_loop(self):
        """Main game loop"""
        while True:
            inp_word = self.get_user_input()
            
            if inp_word is None:
                self.running = False
                sys.exit()
            
            if inp_word in self.word:
                if self.handle_correct_guess(inp_word):
                    break
            else:
                if self.handle_incorrect_guess(inp_word):
                    break
    
    def setup_game(self):
        """Setup the game board"""
        self.show_intro()
        
        # Choose random word
        self.word = random.choice(self.words)
        
        # Setup initial display
        self.update_score_display()
        t.goto(-270, 150)
        t.write("Incorrect guesses:", font=("Arial", 16, "normal"))
        t.update()
        
        # Draw game board
        self.draw_blanks()
        self.create_circles()
    
    def start(self):
        """Start the game"""
        # Start title update thread
        self.title_thread = threading.Thread(target=self.update_title, daemon=True)
        self.title_thread.start()
        
        # Setup and run game
        self.setup_game()
        self.game_loop()
        
        # Cleanup
        self.running = False
        t.done()
        try:
            t.bye()
        except:
            pass

class tik_tak_toe:
    def __init__(self):
        self.cellCenter = {'1':(-200,200),'2':(0,200),'3':(200,200),
                           '4':(-200,0),'5':(0,0),'6':(200,0),
                           '7':(-200,-200),'8':(0,-200),'9':(200,-200)}  
        self.turn = 'black'
        self.round = 0
        self.validMoves = list(self.cellCenter.keys())
        self.occupiedMoves = {'black':[],'red':[]}
        
    def draw_board(self):
        Screen()
        setup(600,600,10,70)
        tracer(False)
        title("Tik Tak Toe")
        bgcolor('light yellow')
        hideturtle()
        pensize(5)
        for i in (-100,100):
            up()
            goto(300,i)
            down()
            goto(-300,i)
            up()
            goto(i,-300)
            down()
            goto(i,300)
            up()
        for cell, center in list(self.cellCenter.items()):
            goto(center)
            write(cell, align='center',font=('Arial',30,'italic'))
    
    def position(self,x,y):
        if -300<x<300 and -300<y<300:
            col = int((x + 300) // 200) + 1
            row = int((y + 300) // 200) + 1
            cell = str((3 - row) * 3 + (col))
            #talk2(f"Marking cell: {cell} for player: {self.turn}")
            #print_say(f'Cell number {cell}')
        else:
            #talk1("Click outside the board")
            return None
        if cell in self.validMoves:
            self.round += 1
            self.validMoves.remove(cell)
            self.occupiedMoves[self.turn].append(cell)
            goto(self.cellCenter[cell])
            dot(120,self.turn)
            if self.winner():
                self.validMoves = []
                messagebox.showinfo("Game over",f'{self.turn} wins!')
                talk2("Game over" + f'{self.turn} wins!')
            elif self.round == 9:
                messagebox.showinfo("Game Over",f"It's a Tie!")
                talk2("Game over",f'It is a tie')
            if self.turn == 'black':
                self.turn = 'red'
            else:
                self.turn = 'black'
        else:
            messagebox.showerror("Invalid Move","Cell already occupied. Choose another cell.") 
            talk2("Invalid Move" + "Cell already occupied. Choose another cell.")  
    def winner(self):
        win = False
        winning_combo = [[str(i) for i in range(1,4)],[str(i) for i in range(4,7)],[str(i) for i in range(7,10)],
                         ['1','4','7'],['2','5','8'],['3','6','9'],['1','5','9'],['3','5','7']]
        for combo in winning_combo:
            if all(i in self.occupiedMoves[self.turn] for i in combo):
            #if all(num in self.cellCenter.keys() and num in self.occupiedMoves[self.turn] for num in i):
                win = True
                break
        return win
    def main(self):
        self.draw_board()
        onscreenclick(self.position)
        done()
        try:
            bye()
        except:
            pass


class ConnectFour:
    def __init__(self):
        """Initialize Game"""

        # Window setup
        self.screen = Screen()
        self.screen.setup(700, 600, 10, 70)
        self.screen.bgcolor("light yellow")
        self.screen.title("Connect Four in Turtle Graphics")

        hideturtle()
        tracer(False)
        pensize(5)

        # Board coordinates
        self.xs = [-300, -200, -100, 0, 100, 200, 300]
        self.ys = [-250, -150, -50, 50, 150, 250]

        # Game state
        self.turn = "red"
        self.occupied = [list() for _ in range(7)]
        self.validinputs = [a for a in range(1, 8)]
        self.rounds = 1

        # Falling disc turtle
        self.fall = Turtle("circle")
        self.fall.hideturtle()
        self.fall.up()

        # Draw board
        self.draw_board()

        # Write column numbers
        self.draw_column_numbers()

        # Bind click
        self.screen.onscreenclick(self.handle_click)
        self.screen.listen()

    # ---------------- BOARD DRAWING ---------------- #

    def draw_board(self):
        """Draw the Connect Four grid"""

        # Vertical lines
        for i in range(-250, 350, 100):
            up()
            goto(i, -350)
            down()
            goto(i, 350)
            up()

        # Horizontal lines
        pensize(1)
        pencolor("grey")
        for i in range(-200, 300, 100):
            up()
            goto(-350, i)
            down()
            goto(350, i)
            up()

        update()

    def draw_column_numbers(self):
        """Draw 1–7 at top"""
        pencolor("black")
        col = 1
        for x in range(-300, 350, 100):
            up()
            goto(x, 270)
            write(col, align="center", font=("Arial", 20, "bold"))
            col += 1
        update()

    # ---------------- WIN CHECKS ---------------- #

    def horizontal4(self, x, y, color, board):
        for dif in (-3, -2, -1, 0):
            try:
                if (board[x + dif][y] == color and
                    board[x + dif + 1][y] == color and
                    board[x + dif + 2][y] == color and
                    board[x + dif + 3][y] == color and
                    x + dif >= 0):
                    return True
            except IndexError:
                pass
        return False

    def vertical4(self, x, y, color, board):
        for dif in (-3, -2, -1, 0):
            try:
                if (board[x][y + dif] == color and
                    board[x][y + dif + 1] == color and
                    board[x][y + dif + 2] == color and
                    board[x][y + dif + 3] == color and
                    y + dif >= 0):
                    return True
            except IndexError:
                pass
        return False

    def forward4(self, x, y, color, board):
        for dif in (-3, -2, -1, 0):
            try:
                if (board[x + dif][y + dif] == color and
                    board[x + dif + 1][y + dif + 1] == color and
                    board[x + dif + 2][y + dif + 2] == color and
                    board[x + dif + 3][y + dif + 3] == color and
                    x + dif >= 0 and y + dif >= 0):
                    return True
            except IndexError:
                pass
        return False

    def back4(self, x, y, color, board):
        for dif in (-3, -2, -1, 0):
            try:
                if (board[x + dif][y - dif] == color and
                    board[x + dif + 1][y - dif - 1] == color and
                    board[x + dif + 2][y - dif - 2] == color and
                    board[x + dif + 3][y - dif - 3] == color and
                    x + dif >= 0 and y - dif - 3 >= 0):
                    return True
            except IndexError:
                pass
        return False

    def diagonal4(self, x, y, color, board):
        """Both diagonal directions combined"""
        # forward /
        if self.forward4(x, y, color, board):
            return True
        # backward \
        if self.back4(x, y, color, board):
            return True
        return False

    def win_game(self, col, row, color, board):
        x = col - 1
        y = row - 1
        return (
            self.horizontal4(x, y, color, board) or
            self.vertical4(x, y, color, board) or
            self.forward4(x, y, color, board) or
            self.back4(x, y, color, board) or
            self.diagonal4(x, y, color, board)
        )

    # ---------------- AI LOGIC ---------------- #

    def computer_best_move(self):
        """Your exact 5-level strategy"""
        occupied = self.occupied
        validinputs = self.validinputs
        turn = self.turn

        # Strategy 1 — center column if empty
        if len(occupied[3]) == 0:
            return 4

        if len(validinputs) == 1:
            return validinputs[0]

        winner = []

        # Strategy 2 — computer wins now?
        for move in validinputs:
            test = deepcopy(occupied)
            test[move - 1].append(turn)
            row = len(test[move - 1])
            if self.win_game(move, row, turn, test):
                winner.append(move)

        if winner:
            return winner[0]

        # Strategy 3 — prevent opponent win next move
        loser = []
        for m1 in validinputs:
            for m2 in validinputs:
                test = deepcopy(occupied)
                test[m1 - 1].append("red")
                test[m2 - 1].append("yellow")
                if self.win_game(m2, len(test[m2 - 1]), "yellow", test):
                    loser.append(m2)

        # Strategy 4 — avoid danger columns
        if loser:
            safe = [m for m in validinputs if m not in loser]
            if safe:
                return choice(safe)

        # Strategy 5 — random fallback
        return choice(validinputs)

    # ---------------- MOVE + ANIMATION ---------------- #

    def make_move(self, col, is_computer=False):
        """Animate + place disc"""

        if col not in self.validinputs:
            return False

        # row number (1 to 6)
        row = len(self.occupied[col - 1]) + 1

        # Animate fall
        if row <= 6:
            for i in range(6, row, -1):
                self.fall.goto(self.xs[col - 1], self.ys[i - 1])
                self.fall.dot(80, self.turn)
                update()
                sleep(0.08)
                self.fall.clear()

        # Place permanently
        up()
        goto(self.xs[col - 1], self.ys[row - 1])
        dot(80, self.turn)
        update()

        self.occupied[col - 1].append(self.turn)

        # Win check
        if self.win_game(col, row, self.turn, self.occupied):
            self.validinputs.clear()
            winner = "Computer" if is_computer else "Player"
            messagebox.showinfo("Game Over", f"{winner} ({self.turn}) wins!")
            sys.exit()

        # Tie check
        if self.rounds == 42:
            messagebox.showinfo("Game Over", "It's a draw!")
            sys.exit()

        # Update availability
        if len(self.occupied[col - 1]) == 6:
            if col in self.validinputs:
                self.validinputs.remove(col)

        # Turn switch
        self.turn = "yellow" if self.turn == "red" else "red"
        self.rounds += 1
        return True

    # ---------------- INPUT HANDLING ---------------- #

    def handle_click(self, x, y):
        """Handle user click, then computer move"""

        # Check click inside board
        if not (-350 < x < 350 and -350 < y < 350):
            return

        col = int((x + 350) // 100) + 1

        if col not in self.validinputs:
            messagebox.showinfo("Invalid Move", "Column full!")
            return

        # Player move
        self.make_move(col, is_computer=False)

        # Computer move (if game not over)
        if self.validinputs:
            sleep(0.5)
            comp_col = self.computer_best_move()
            self.make_move(comp_col, is_computer=True)

    # ---------------- START GAME ---------------- #

    def start(self):
        self.screen.mainloop()

def take_command():
    return input(">>> ").lower().strip()

def show_alert(text, title="Info"):
    import tkinter.messagebox as mb
    mb.showinfo(title, text)


class ConnectFourTwoPlayer:
    def __init__(self):
        """Initialize the 2-player Connect Four game"""
        # Setup screen
        self.screen = Screen()
        self.screen.setup(700, 600, 10, 70)
        self.screen.bgcolor('light yellow')
        self.screen.title("Connect Four in Turtle Graphics - 2 Players")
        
        # Setup main turtle
        hideturtle()
        tracer(False)
        
        # Game state
        self.turn = 'red'  # Red player moves first
        self.xs = [-300, -200, -100, 0, 100, 200, 300]  # X-coords of 7 columns
        self.ys = [-250, -150, -50, 50, 150, 250]  # Y-coords of 6 rows
        self.occupied = [list() for _ in range(7)]  # Track occupied cells
        self.validinputs = [1, 2, 3, 4, 5, 6, 7]  # Valid column inputs
        self.rounds = 1
        
        # Create animation turtle
        self.fall = Turtle()
        self.fall.up()
        self.fall.hideturtle()
        
        # Draw the board
        self.draw_board()
        
        # Setup click handler
        self.screen.onscreenclick(self.handle_click)
        self.screen.listen()
    
    def draw_board(self):
        """Draw the game board"""
        # Draw vertical lines
        pensize(5)
        for i in range(-250, 350, 100):
            up()
            goto(i, -350)
            down()
            goto(i, 350)
            up()
        
        # Draw horizontal lines
        pensize(1)
        pencolor('grey')
        for i in range(-200, 300, 100):
            up()
            goto(-350, i)
            down()
            goto(350, i)
            up()
        
        # Draw column numbers
        pencolor('black')
        col = 1
        for x in range(-300, 350, 100):
            up()
            goto(x, 270)
            write(col, font=('Arial', 20, 'normal'))
            col += 1
        
        update()
    
    def horizontal4(self, x, y, turn):
        """Check for 4 connected horizontally"""
        win = False
        for dif in (-3, -2, -1, 0):
            try:
                if (self.occupied[x+dif][y] == turn and 
                    self.occupied[x+dif+1][y] == turn and
                    self.occupied[x+dif+2][y] == turn and 
                    self.occupied[x+dif+3][y] == turn and 
                    x + dif >= 0):
                    win = True
            except IndexError:
                pass
        return win
    
    def vertical4(self, x, y, turn):
        """Check for 4 connected vertically"""
        win = False
        try:
            if (self.occupied[x][y] == turn and
                self.occupied[x][y-1] == turn and
                self.occupied[x][y-2] == turn and
                self.occupied[x][y-3] == turn and
                y-3 >= 0):
                win = True
        except IndexError:
            pass
        return win
    
    def forward4(self, x, y, turn):
        """Check for 4 connected diagonally (/)"""
        win = False
        for dif in (-3, -2, -1, 0):
            try:
                if (self.occupied[x+dif][y+dif] == turn and
                    self.occupied[x+dif+1][y+dif+1] == turn and
                    self.occupied[x+dif+2][y+dif+2] == turn and
                    self.occupied[x+dif+3][y+dif+3] == turn and
                    x+dif >= 0 and y+dif >= 0):
                    win = True
            except IndexError:
                pass
        return win
    
    def back4(self, x, y, turn):
        """Check for 4 connected diagonally (\\)"""
        win = False
        for dif in (-3, -2, -1, 0):
            try:
                if (self.occupied[x+dif][y-dif] == turn and
                    self.occupied[x+dif+1][y-dif-1] == turn and
                    self.occupied[x+dif+2][y-dif-2] == turn and
                    self.occupied[x+dif+3][y-dif-3] == turn and
                    x+dif >= 0 and y-dif-3 >= 0):
                    win = True
            except IndexError:
                pass
        return win
    
    def win_game(self, col, row, turn):
        """Check if current move wins the game"""
        x = col - 1
        y = row - 1
        
        return (self.vertical4(x, y, turn) or 
                self.horizontal4(x, y, turn) or 
                self.forward4(x, y, turn) or 
                self.back4(x, y, turn))
    
    def animate_drop(self, col, row, color):
        """Animate disc falling"""
        if row <= 6:
            for i in range(6, row, -1):
                self.fall.goto(self.xs[col - 1], self.ys[i - 1])
                self.fall.dot(80, color)
                update()
                sleep(0.08)
                self.fall.clear()
    
    def place_disc(self, col, row, color):
        """Place a disc on the board"""
        up()
        goto(self.xs[col - 1], self.ys[row - 1])
        dot(80, color)
        self.occupied[col - 1].append(color)
        update()
    
    def check_game_end(self, col, row):
        """Check if game ended (win or tie)"""
        if self.win_game(col, row, self.turn):
            self.validinputs = []
            messagebox.showinfo("End Game", f'Congrats player {self.turn}, you Won!!!')
            return True
        elif self.rounds == 42:
            messagebox.showinfo("Tie Game", "Game over, it's a tie!")
            return True
        return False
    
    def switch_turn(self):
        """Switch between red and yellow"""
        self.turn = 'yellow' if self.turn == 'red' else 'red'
    
    def handle_click(self, x, y):
        """Handle mouse click on the board"""
        # Check if click is within board
        if not (-350 < x < 350 and -350 < y < 350):
            print("You clicked outside the game board")
            return
        
        # Calculate column
        col = int((x + 350) // 100) + 1
        
        # Check if column is valid
        if col not in self.validinputs:
            messagebox.showerror("Error", "Sorry, that's an invalid move!")
            return
        
        # Calculate row
        row = len(self.occupied[col - 1]) + 1
        
        # Check if column is full
        if row > 6:
            messagebox.showerror("Error", "This column is full!")
            return
        
        # Animate and place disc
        self.animate_drop(col, row, self.turn)
        self.place_disc(col, row, self.turn)
        
        # Check if game ended
        if self.check_game_end(col, row):
            return
        
        # Update game state
        self.rounds += 1
        if len(self.occupied[col - 1]) == 6:
            self.validinputs.remove(col)
        
        # Switch to next player
        self.switch_turn()
    
    def start(self):
        """Start the game loop"""
        self.screen.mainloop()

def coin(currency="bitcoin"):
    """
    Display live cryptocurrency price tracker
    
    Parameters:
    currency: cryptocurrency name (e.g., 'bitcoin', 'ethereum', 'dogecoin')
    """
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={currency}&vs_currencies=usd"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    root = tk.Tk()
    root.title(f"{currency.title()} Watch")
    root.geometry("400x200")
    
    label1 = tk.Label(root, text='', fg='Blue', font=("Helvetica", 30))
    label1.pack()
    
    label2 = tk.Label(root, text='', fg='Red', font=("Helvetica", 26))
    label2.pack()
    
    def update_price():
        """Update the price display"""
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            
            if currency in data:
                price = data[currency]['usd']
                
                # Update datetime
                label1.configure(text=f"{arrow.now().format('DD-MM-YYYY')}\n{arrow.now().format('HH:mm:ss A')}")
                # Update price
                label2.configure(text=f"{currency.title()}: ${price:,.2f}", justify=tk.LEFT)
            else:
                label2.configure(text=f"Currency '{currency}' not found")
            
            # Call again after 1000ms
            root.after(1000, update_price)
        
        except Exception as e:
            label2.configure(text=f"Error: {str(e)}")
            root.after(5000, update_price)  # Retry after 5 seconds
    # Start updating
    update_price()
    # Start GUI loop
    root.mainloop()

def get_ticker_from_company(company_name):
    """Get stock ticker symbol from company name using Yahoo Finance API"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={company_name}"
        response = requests.get(url, headers=headers, timeout=10)
        res = response.json()
        
        if res.get('quotes') and len(res['quotes']) > 0:
            symbol = res['quotes'][0]['symbol']
            return symbol
        else:
            talk2("No ticker found for that company name!")
            return None
    except Exception as e:
        talk1(f"Error retrieving ticker: {e}")
        return None

def stock(ticker=None, company_name=None):
    """
    Display stock price and historical graph
    Parameters:
    ticker: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
    company_name: Company name (e.g., 'Apple', 'Google') - will be converted to ticker
    """
    
    # If company name is provided, get ticker symbol
    if company_name:
        talk2(f"Looking up ticker for {company_name}...")
        ticker = get_ticker_from_company(company_name)
        if ticker is None:
            return
    
    # Default to AMZN if no ticker provided
    if ticker is None:
        ticker_symbol = "AMZN"
        talk2("No ticker provided, using default: AMZN")
    else:
        ticker_symbol = ticker
    
    try:
        stock_obj = yf.Ticker(ticker_symbol)
        
        # Get current price and company info
        price = stock_obj.info.get("regularMarketPrice")
        company_full_name = stock_obj.info.get("longName", ticker_symbol)
        
        if price is None:
            talk1(f"Could not retrieve price for {ticker_symbol}")
            return
        
        say = f"{company_full_name} (Ticker: {ticker_symbol}) has stock price ${price}"
        talk2(say)
        
        # Set date range - last 30 days to today
        e_date = arrow.now().format("YYYY-MM-DD")
        s_date = arrow.now().shift(days=-30).format("YYYY-MM-DD")
        
        talk2(f"Fetching data from {s_date} to {e_date}...")
        
        # Get historical data
        data = stock_obj.history(start=s_date, end=e_date)
        
        # Check if data is empty
        if data.empty:
            talk1("No data retrieved! Check your ticker symbol and dates.")
            return
        
        print(data)
        
        # Reset index to convert Date from index to column
        data = data.reset_index()
        
        # Convert dates to matplotlib format
        data['Date_num'] = mdates.date2num(data['Date'])
        
        # Create figure with size and DPI
        fig, ax = plt.subplots(figsize=(10, 6), dpi=128)
        
        # Format date for x-axis
        formatter = mdates.DateFormatter('%m/%d/%Y')
        ax.xaxis.set_major_formatter(formatter)
        
        # Plot data
        ax.plot(data['Date_num'], data['Close'], c='blue', linewidth=2, label='Close Price')
        
        # Format plot
        ax.set_title(f"Stock Price of {company_full_name} ({ticker_symbol})", 
                     fontsize=16, fontweight='bold')
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel("Price ($)", fontsize=12)
        
        # Auto-format x-axis date labels
        fig.autofmt_xdate(rotation=45)
        
        # Add grid for better readability
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        plt.tight_layout()
        plt.show()
        
    except Exception as e:
        talk2(f"Error: {e}")
        talk1("Sorry, not a valid entry!")

class TurtleTranslator:
    def __init__(self):
        """Initialize the turtle translator"""
        # Setup screen
        self.screen = t.Screen()
        self.screen.setup(800, 600)
        self.screen.bgcolor('light blue')
        self.screen.title("Turtle Dictionary Translator")
        
        # Create turtle for writing
        self.writer = t.Turtle()
        self.writer.hideturtle()
        self.writer.up()
        self.writer.speed(0)
        
        # Create translator
        self.translator = Translator()
        
        # Language codes
        self.lang_abbre = {
            "english": "en",
            "chinese": "zh",
            "spanish": "es",
            "french": "fr",
            "japanese": "ja",
            "portuguese": "pt",
            "russian": "ru",
            "korean": "ko",
            "german": "de",
            "italian": "it",
            "bangla": "bn"
        }
        
        # Draw interface
        self.draw_interface()
    
    def draw_interface(self):
        """Draw the main interface"""
        self.writer.clear()
        
        # Title
        self.writer.goto(0, 250)
        self.writer.write("Dictionary Translator", align="center", font=("Arial", 24, "bold"))
        
        # Instructions
        self.writer.goto(0, 200)
        self.writer.write("Enter English text to translate", align="center", font=("Arial", 14, "normal"))
        
        # Available languages
        self.writer.goto(0, 150)
        langs = ", ".join(self.lang_abbre.keys())
        self.writer.write(f"Available languages:", align="center", font=("Arial", 12, "normal"))
        
        self.writer.goto(0, 130)
        self.writer.write(langs, align="center", font=("Arial", 10, "normal"))
        
        t.update()
    
    def text_to_speech(self, text, lang_code):
        """Convert text to speech and play it"""
        try:
            tts = gTTS(text=text, lang=lang_code)
            voice = BytesIO()
            tts.write_to_fp(voice)
            voice.seek(0)
            play(AudioSegment.from_mp3(voice))
        except Exception as e:
            self.show_message(f"Audio Error: {str(e)}", -50, "red")
    
    def translate_text(self, text, target_lang):
        """Translate text to target language"""
        try:
            result = self.translator.translate(text, dest=target_lang)
            return result.text
        except Exception as e:
            return f"Translation Error: {str(e)}"
    
    def show_message(self, message, y_pos, color="black"):
        """Display a message on screen"""
        self.writer.goto(0, y_pos)
        self.writer.color(color)
        self.writer.write(message, align="center", font=("Arial", 16, "bold"))
        self.writer.color("black")
        t.update()
    
    def run(self):
        """Main translation loop"""
        while True:
            # Get English input
            english_text = t.textinput("Input", "Enter English text (or 'quit' to exit):")
            
            if english_text is None or english_text.lower() == 'quit':
                break
            
            if not english_text.strip():
                continue
            
            # Get target language
            target_lang = t.textinput("Language", "Enter target language:\n(english, bangla, french, german, etc.)")
            
            if target_lang is None or target_lang.lower() == 'quit':
                break
            
            target_lang = target_lang.lower().strip()
            
            if target_lang not in self.lang_abbre:
                self.draw_interface()
                self.show_message("Invalid language! Please try again.", 50, "red")
                continue
            
            # Clear previous results
            self.draw_interface()
            
            # Show original text
            self.writer.goto(0, 50)
            self.writer.write(f"English: {english_text}", align="center", font=("Arial", 14, "normal"))
            
            # Translate
            lang_code = self.lang_abbre[target_lang]
            translated_text = self.translate_text(english_text, lang_code)
            
            # Show translation
            self.writer.goto(0, 0)
            self.writer.color("blue")
            self.writer.write(f"{target_lang.title()}: {translated_text}", align="center", font=("Arial", 16, "bold"))
            self.writer.color("black")
            
            t.update()
            
            # Ask if user wants to hear it
            #play_audio = t.textinput("Audio", "Play audio? (yes/no):")
            #if play_audio and play_audio.lower() in ['yes', 'y']:
            self.show_message("Playing audio...", -50, "green")
            self.text_to_speech(translated_text, lang_code)
            self.writer.goto(0, -50)
            self.writer.clear()
        
        # Cleanup
        t.bye()

class BanglaVoiceTranslator:
    def __init__(self):
        """Initialize the Bangla voice translator"""
        self.speech = sr.Recognizer()
        self.translator = Translator()
        
        # Initialize text-to-speech engine
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)
        self.engine.setProperty('volume', 0.9)
    
    def speak(self, text):
        """Speak the text"""
        print(f"Reply: {text}")
        self.engine.say(text)
        self.engine.runAndWait()
    
    def listen_bangla(self):
        """Listen and recognize Bangla speech"""
        talk1('Python is listening in Bangla...')
        
        with sr.Microphone() as source:
            self.speech.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = self.speech.listen(source, timeout=5)
                bangla_text = self.speech.recognize_google(audio, language="bn")
                talk2(f"You said (Bangla): {bangla_text}")
                return bangla_text
            except sr.WaitTimeoutError:
                print("No speech detected")
                return None
            except sr.UnknownValueError:
                print("Could not understand audio")
                return None
            except sr.RequestError as e:
                print(f"Could not request results; {e}")
                return None
    
    def translate_to_english(self, bangla_text):
        """Translate Bangla text to English"""
        try:
            result = self.translator.translate(bangla_text, src='bn', dest='en')
            english_text = result.text
            talk1(f"Translated to English: {english_text}")
            return english_text
        except Exception as e:
            print(f"Translation error: {e}")
            return None
    
    def generate_reply(self, english_text):
        """Generate simple replies based on English text"""
        text_lower = english_text.lower()
        
        # Greetings
        if any(word in text_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good evening']):
            return "Hello! How can I help you today?"
        
        # How are you
        elif any(word in text_lower for word in ['how are you', 'how do you do']):
            return "I'm doing great! Thank you for asking. How about you?"
        
        # Name questions
        elif 'your name' in text_lower or 'who are you' in text_lower:
            return "I am a Bangla voice translator. I can understand Bangla and reply in English."
        
        # Time
        elif 'time' in text_lower and 'what' in text_lower:
            from datetime import datetime
            current_time = datetime.now().strftime('%I:%M %p')
            return f"The current time is {current_time}"
        
        # Date
        elif 'date' in text_lower and ('what' in text_lower or 'today' in text_lower):
            from datetime import datetime
            current_date = datetime.now().strftime('%B %d, %Y')
            return f"Today's date is {current_date}"
        
        # Weather
        elif 'weather' in text_lower:
            return "I cannot check the weather right now, but you can check online weather services."
        
        # Thank you
        elif any(word in text_lower for word in ['thank you', 'thanks', 'thank']):
            return "You're welcome! Happy to help!"
        
        # Goodbye
        elif any(word in text_lower for word in ['bye', 'goodbye', 'see you', 'quit', 'exit']):
            return "Goodbye! Have a great day!"
        
        # Help
        elif 'help' in text_lower:
            return "I can answer simple questions. Try asking me about time, date, or just say hello!"
        
        # Default response
        else:
            return f"I heard you say: {english_text}. I'm still learning to respond to this!"
    
    def run(self):
        """Main loop"""
        self.speak("Bangla voice translator is ready. Please speak in Bangla.")
        
        while True:
            # Listen to Bangla
            bangla_text = self.listen_bangla()
            
            if bangla_text is None:
                continue
            
            # Translate to English
            english_text = self.translate_to_english(bangla_text)
            
            if english_text is None:
                continue
            
            # Check for exit command
            if any(word in english_text.lower() for word in ['bye', 'goodbye', 'quit', 'exit']):
                reply = self.generate_reply(english_text)
                self.speak(reply)
                break
            
            # Generate and speak reply
            reply = self.generate_reply(english_text)
            self.speak(reply)
            print("-" * 50)

def me():
    screenshot_path = "/tmp/marin_screenshot.png"
    subprocess.run(["scrot", "-s", screenshot_path], capture_output=True)
    screenshot = Image.open(screenshot_path)
    # Settings
    scale = 0.8
    threshold = 128
    # Convert screenshot to grayscale (no need to reopen file)
    img = screenshot.convert("L")
    # Resize image
    img = img.resize((int(img.width * scale), int(img.height * scale)))
    # Creating a blank white canvas
    im = Image.new('RGBA', (img.width, img.height), 'white')
    draw = ImageDraw.Draw(im)
    # Step 4: Convert to stencil
    for y in range(img.height):
        for x in range(img.width):
            if img.getpixel((x, y)) < threshold:
                draw.point((x, y), fill='black')
    # Step 5: Show result
    im.show()


def draw():
    """Take screenshot and draw it with turtle animation"""
    screenshot_path = "/tmp/marin_screenshot.png"
    subprocess.run(["scrot", "-s", screenshot_path], capture_output=True)
    screenshot = Image.open(screenshot_path)
    
    # Convert screenshot to grayscale + RGB for turtle
    scale = 0.25
    dot_size = 2
    img = screenshot.convert("L")
    img = img.resize((int(img.width * scale), int(img.height * scale)))
    img = img.convert("RGB")
    
    # ========================================
    # START SCREEN
    # ========================================
    screen = Screen()
    screen.colormode(255)
    screen.setup(int(img.width * dot_size) + 50, int(img.height * dot_size) + 50, 100, 50)
    screen.bgcolor('light yellow')
    screen.tracer(True)
    
    # Create animation turtle
    c = Turtle('turtle')
    c.shapesize(1)
    c.color("black", "red")
    c.speed(0)
    
    # Create main drawing turtle
    main_turtle = Turtle()
    main_turtle.shape('turtle')
    main_turtle.speed(0)
    
    colors = [
        (255, 182, 193), (173, 216, 230), (152, 251, 152),
        (230, 230, 250), (255, 218, 185), (255, 255, 224),
        (135, 206, 235), (240, 128, 128), (255, 253, 208),
        (200, 162, 200), (211, 211, 211), (245, 245, 220),
        (255, 255, 240), (255, 218, 185), (175, 238, 238),
        (176, 224, 230)
    ]
    
    width, height = img.size
    i = int(width * dot_size / 2)
    j = int(height * dot_size / 2)
    
    # ========================================
    # ANIMATION SEQUENCE
    # ========================================
    for _ in range(4):
        for k in range(-i, i, 20):
            c.shape(random.choice(['turtle', 'circle', 'arrow', 'square', 'triangle', 'classic']))
            main_turtle.shape(random.choice(['turtle', 'circle', 'arrow', 'square', 'triangle', 'classic']))
            
            main_turtle.speed(0.0001)
            main_turtle.color("black", random.choice(colors))
            
            c.speed(0.0001)
            c.color("black", random.choice(colors))
            c.goto(k, random.randint(-j, j))
            
            main_turtle.pensize(random.randint(1, 4))
            main_turtle.pencolor(random.choice(colors))
            main_turtle.goto(k, random.randint(-j, j))
            
            sleep(0.005)
            c.color("black", random.choice(colors))
            main_turtle.dot(10)
        
        c.goto(100, 0)
        sleep(0.5)
    
    c.hideturtle()
    main_turtle.hideturtle()
    
    # ========================================
    # DRAW THE SCREENSHOT
    # ========================================
    x_offset = -width * dot_size / 2
    y_offset = height * dot_size / 2
    bright_colors = ['white', 'light yellow']
    dark_colors = ['black', 'darkblue']
    
    t = Turtle()
    t.hideturtle()
    t.up()
    t.speed(0)
    screen.tracer(False)  # Turn off animation for faster drawing
    
    print("Drawing screenshot...")
    for y in range(height):
        for x in range(width):
            r, g, b = img.getpixel((x, y))
            draw_x = x * dot_size + x_offset
            draw_y = y_offset - y * dot_size
            
            # Choose color based on brightness
            if r > 127:
                color = random.choice(bright_colors)
            else:
                color = random.choice(dark_colors)
            
            t.goto(draw_x, draw_y)
            t.dot(dot_size, color)
        
        # Update screen periodically to show progress
        if y % 10 == 0:
            screen.update()
    
    screen.tracer(True)
    screen.update()
    
    messagebox.showinfo("Done", "Drawing completed!")
    print("Drawing complete")
    
    screen.mainloop()
    
# Dictionary of applications and their commands
APPS = {
    # Browsers
    "chrome": "xdg-open https://chrome.google.com",
    "google chrome": "google-chrome",
    "firefox": "firefox",
    "edge": "microsoft-edge",
    "brave": "brave-browser",

    # Office Apps
    "word": "libreoffice --writer",
    "excel": "libreoffice --calc",
    "powerpoint": "libreoffice --impress",
    "notepad": "gedit",
    "calculator": "gnome-calculator",
    "paint": "gimp",

    # Communication
    "zoom": "zoom",
    "teams": "teams",
    "skype": "skypeforlinux",
    "whatsapp": "whatsdesk",

    # Media
    "spotify": "spotify",
    "vlc": "vlc",
    "gimp": "gimp",

    # Development
    "visual studio code": "code",
    "vscode": "code",
    "vs code": "code",
    "pycharm": "pycharm",
    "sublime": "subl",
    "atom": "atom",

    # System
    "task manager": "gnome-system-monitor",
    "control panel": "gnome-control-center",
    "settings": "gnome-control-center",
    "file explorer": "nautilus",
    "command prompt": "gnome-terminal",
    "terminal": "gnome-terminal",
    "powershell": "pwsh",

    # Other
    "steam": "steam",
    "epic games": " epicgameslauncher",
}

# Dictionary of web applications (browser-based)
WEB_APPS = {
    # AI Chatbots
    "claude": "https://claude.ai",
    "chatgpt": "https://chat.openai.com",
    "chat gpt": "https://chat.openai.com",
    "gpt": "https://chat.openai.com",
    "grok": "https://x.com/i/grok",
    "gemini": "https://gemini.google.com",
    "copilot": "https://copilot.microsoft.com",
    
    # Social Media
    "youtube": "https://www.youtube.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "reddit": "https://www.reddit.com",
    "telegram": "https://web.telegram.org/k/",
    
    # Productivity
    "gmail": "https://mail.google.com",
    "google docs": "https://docs.google.com",
    "google sheets": "https://sheets.google.com",
    "google drive": "https://drive.google.com",
    "notion": "https://www.notion.so",
    "trello": "https://trello.com",
    
    # Other
    "git": "https://github.com",
    "geet": "https://github.com",
    
    "stackoverflow": "https://stackoverflow.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.com",
    "daraz": "https://www.daraz.com.bd/?no_webview_showup_reload=true#?"
}

def run_alexa(command):
    print(command)
    
    if 'play' in command:
        command = command.replace('play', '')
        talk1(f"Playing {command} on YouTube")
        print(f"Playing {command} on YouTube")
        pywhatkit.playonyt(command)
    
    elif 'time' in command:
        time = datetime.datetime.now().strftime('%I:%M %p')
        talk1("The current time is " + time)
        print("The current time is " + time)
    
    elif 'date' in command:
        date = datetime.datetime.now().strftime('%B %d, %Y')
        talk1("Today's date is " + date)
        print("Today's date is " + date)
    
    elif 'are you single' in command:
        talk1("I am in a relationship with WiFi")
        print("I am in a relationship with WiFi")
    
    elif 'press' in command:
        command = command.replace('press ', '')
        subprocess.run(["xdotool", "key", command], capture_output=True)
    
    elif 'type' in command:
        command = command.replace('type ', '')
        subprocess.run(["xdotool", "type", "--", command], capture_output=True)
    
    elif 'cancel' in command or 'stop program' in command :
        talk2("Canceling program")
        time.sleep(0.1)
        subprocess.run(["xdotool", "key", "Alt+F4"], capture_output=True)
    
    elif 'show me' in command:
        me()
    
    elif 'map' in command:
        command = command.replace('map ', '')
        parts = command.split()
        if len(parts) == 2:
            subprocess.run(["xdotool", "key", parts[0], parts[1]], capture_output=True)
    
    elif 'timer for' in command and ("hour" in command or "minute" in command or "second" in command):
        threading.Thread(target=timer, args=(command,), daemon=True).start()
    
    elif 'google' in command:
        query = command.replace('google ', '')
        import webbrowser, urllib.parse
        url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
        webbrowser.open(url)
        talk1(f"Searching Google for: {query}")

    
    elif 'screenshot' in command or 'take screenshot' in command:
        talk1("Taking screenshot")
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        subprocess.run(["scrot", filename], capture_output=True)
        talk1(f"Screenshot saved as {filename}")
        print(f"Screenshot saved: {filename}")
    
    elif 'alarm for' in command and ("a.m." in command or "p.m." in command):
        threading.Thread(target=alarm, args=(command,), daemon=True).start()
    
    elif 'send' in command and "email" in command:
        threading.Thread(target=email, daemon=True).start()
    
    elif 'joke' in command:
        joke = pyjokes.get_joke()
        talk1(joke)
        threading.Thread(target=show_alert, args=(joke, 'Python Jokes')).start()
    
    elif 'news' in command:
        threading.Thread(target=news, daemon=True).start()
    
    elif 'bangla' in command:
        talk1("Starting Bangla voice translator")
        translator = BanglaVoiceTranslator()
        threading.Thread(target=translator.run, daemon=True).start()
    
    elif 'download' in command:
        talk2("Enter link of the video/audio")
        link = textinput("Enter Link", "Paste YouTube URL:")
        if link:
            try:
                talk2("Downloading, please wait...")
                os.system(f"yt-dlp {link}")
                talk2("The video has been downloaded")
            except Exception as e:
                talk1("This is not a valid link")
    
    elif 'draw me' in command:
        talk1("Taking photo and drawing")
        threading.Thread(target=draw, daemon=True).start()
    
    elif 'instruction' in command:
        instructions = f'>Time instructions: {timer_instruction()}\n\
>Alarm instructions: {alarm_instructions()}\n\
>Say play "video name" to play YouTube videos\n\
>Say time to see current time\n\
>Say date to see today\'s date\n\
>Say joke to hear jokes\n\
>Say send email to send an email\n\
>Say press [key] to press any keyboard key\n\
>Say type [text] to type automatically\n\
>Say cancel or stop to close programs\n\
>Say open [app name] to launch applications\n\
>Say show me to open personal info\n\
>Say draw me to draw the screenshot\n\
>Say map [key1 key2] to run keyboard shortcuts\n\
>Say timer for [X seconds/minutes/hours] to set a timer\n\
>Say google [your query] to search on Google\n\
>Say screenshot or take screenshot to capture screen\n\
>Say alarm for [time a.m./p.m.] to set alarm\n\
>Say news to hear or view news\n\
>Say bangla to start Bangla voice translator\n\
>Say download to download YouTube videos\n\
>Say tik tak toe to play Tic-Tac-Toe\n\
>Say connect computer to play Connect Four vs computer\n\
>Say connect to play Connect Four two-player\n\
>Say word game to play Guess-The-Word\n\
>Say market for [company] to get stock info\n\
>Say price of [crypto] to track live cryptocurrency price\n\
>Say dictionary to open the dictionary app\n\
>Say stop to exit\n\
>Say open to open any program\n\
>You can also ask questions like history, weather, places, etc.'
        
        threading.Thread(target=show_alert, args=(instructions, "Alexa Instructions")).start()
    
    # GAMES - All need threading for turtle/tkinter
    elif 'tik' in command and ('tak' in command or 'toe' in command):
        talk1("Starting Tic Tac Toe game")
        def start_tiktaktoe():
            game = tik_tak_toe()
            game.main()
        threading.Thread(target=start_tiktaktoe, daemon=True).start()
    
    elif 'connect' in command and 'computer' in command:
        talk1("Starting Connect Four against computer")
        #def start_connect_computer():
        ConnectFour().start()
    #    threading.Thread(target=start_connect_computer, daemon=True).start()
    
    elif 'connect' in command:
        talk1("Starting Connect Four two player")
        def start_connect_two():
            game = ConnectFourTwoPlayer()
            game.start()
        threading.Thread(target=start_connect_two, daemon=True).start()
    
    elif 'word' in command and 'game' in command:
        talk1("Starting Guess The Word game")
        def start_word_game():
            game = GuessTheWordGame()
            game.start()
        threading.Thread(target=start_word_game, daemon=True).start()
    
    # STOCK - needs threading for matplotlib
    elif 'market' in command and 'for' in command:
        pos = command.find('market for')
        company = command[pos + len('market for'):].strip()
        #talk1(f"Looking up stock information for {company}")
        threading.Thread(target=stock, kwargs={'company_name': company}, daemon=True).start()
    
    # CRYPTO - needs threading for tkinter
    elif 'price of' in command:
        pos = command.find('price of')
        if pos != -1:
            crypto = command[pos + len('price of'):].strip()
            talk1(f"Opening {crypto} price watch")
            threading.Thread(target=coin, args=(crypto,), daemon=True).start()
    
    # DICTIONARY - needs threading for turtle
    elif 'dictionary' in command:
        talk1("Opening dictionary translator")
        def start_dictionary():
            app = TurtleTranslator()
            app.run()
        threading.Thread(target=start_dictionary, daemon=True).start()
    
    elif 'stop' in command and 'alexa' not in command:
        talk1("Goodbye!")
        tts_queue.join()
        import sys
        sys.exit()
    
    # APP LAUNCHER
    elif 'open' in command:
        # Extract app name after "open"
        app_name = command.replace('open', '').strip()
        
        # Check if it's a desktop app
        if app_name in APPS:
            talk1(f"Opening {app_name}")
            try:
                subprocess.Popen(APPS[app_name], shell=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"Opened: {app_name}")
            except Exception as e:
                talk1(f"Could not open {app_name}")
                print(f"Error: {e}")
        
        # Check if it's a web app
        elif app_name in WEB_APPS:
            talk1(f"Opening {app_name} in browser")
            try:
                import webbrowser
                webbrowser.open(WEB_APPS[app_name])
                print(f"Opened: {app_name} at {WEB_APPS[app_name]}")
            except Exception as e:
                talk1(f"Could not open {app_name}")
                print(f"Error: {e}")
        
        else:
            talk1(f"I don't know how to open {app_name}. Please add it to my app dictionary.")
            print(f"Available desktop apps: {', '.join(APPS.keys())}")
            print(f"Available web apps: {', '.join(WEB_APPS.keys())}")
    
    else:
        if len(command) > 6:
            talk1(f"Searching for {command}")
            threading.Thread(target=know_all, args=(command,), daemon=True).start()

def main():
    while True:
        command = take_command()
        if command:
            threading.Thread(target=run_alexa, args=(command,)).start()

if __name__ == '__main__':
    # Start the TTS worker thread
    tts_thread = threading.Thread(target=tts_worker, daemon=True)
    tts_thread.start()
    
    instructions = instructions = f'>Time instructions: {timer_instruction()}\n\
>Alarm instructions: {alarm_instructions()}\n\
>Say play "video name" to play YouTube videos\n\
>Say time to see current time\n\
>Say date to see today\'s date\n\
>Say joke to hear jokes\n\
>Say send email to send an email\n\
>Say press [key] to press any keyboard key\n\
>Say type [text] to type automatically\n\
>Say cancel or stop to close programs\n\
>Say show me to open personal info\n\
>Say draw me to draw the screenshot\n\
>Say map [key1 key2] to run keyboard shortcuts\n\
>Say timer for [X seconds/minutes/hours] to set a timer\n\
>Say google [your query] to search on Google\n\
>Say screenshot or take screenshot to capture screen\n\
>Say alarm for [time a.m./p.m.] to set alarm\n\
>Say news to hear or view news\n\
>Say bangla to start Bangla voice translator\n\
>Say download to download YouTube videos\n\
>Say tik tak toe to play Tic-Tac-Toe\n\
>Say connect computer to play Connect Four vs computer\n\
>Say connect to play Connect Four two-player\n\
>Say word game to play Guess-The-Word\n\
>Say market for [company] to get stock info\n\
>Say price of [crypto] to track live cryptocurrency price\n\
>Say dictionary to open the dictionary app\n\
>Say stop to exit\n\
>Say open to open any program\n\
>You can also ask questions like history, weather, places, etc.'
    
    talk2("Hello I'm Alexa! How can I help you")
    threading.Thread(target=show_alert, args=(instructions, "Manual for using VPA")).start()
    main()