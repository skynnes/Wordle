from readline import read_history_file
import os
import requests

from regex import P
from words import get_wordle_guesses, get_wordle_answers, get_wordmaster_guesses, get_wordmaster_answers
import time 
from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import numpy as np
from tempfile import mkdtemp


def handler(event=None, context=None):
    options = webdriver.ChromeOptions()
    options.binary_location = '/opt/chrome/chrome'
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280x1696")
    options.add_argument("--single-process")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-dev-tools")
    options.add_argument("--no-zygote")
    options.add_argument(f"--user-data-dir={mkdtemp()}")
    options.add_argument(f"--data-path={mkdtemp()}")
    options.add_argument(f"--disk-cache-dir={mkdtemp()}")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--incognito")
    chrome = webdriver.Chrome("/opt/chromedriver",
                              options=options)
    # chrome = webdriver.Chrome(ChromeDriverManager().install(), options=options)
    result = run_program(chrome)
    return result

def play(game_rows, browser, possible_guesses, possible_answers, keyboard, classic_wordle=True):
    # get the word list
    words = possible_guesses
    narrowed_down_list = possible_answers
    score = []

    for guess_number in range(5):
        # goal is to minimize the longest possible word list after guess & evaluation
        # start this metric at a million (we have under 100k words)
        min_wordcount = 1e6
        chosen_word = ""
        evaluation_to_wordlist_map = {}
        
        
        if guess_number != 0:
            words_to_consider = words
        else:
            # first guess doesn't change
            # there are many "good" first guesses
            # best words: https://www.polygon.com/gaming/22884031/wordle-game-tips-best-first-guess-5-letter-words
            words_to_consider = ["arise"]
    
        # check every word in words_to_consider to see which one gives us most information
        # (allows us to cancel out the most words)
        for word_to_guess in words_to_consider:
            temp_eval_to_words_map = {}
            
            # evaluate with every possible answer
            for possible_answer in narrowed_down_list:
                evaluation = get_evaluation(possible_answer, word_to_guess)
                        
                # store word by evaluation tuple in a list
                if tuple(evaluation) not in temp_eval_to_words_map:
                    temp_eval_to_words_map[tuple(evaluation)] = [possible_answer]
                else:
                    temp_eval_to_words_map[tuple(evaluation)].append(possible_answer)
    
    
            # metric we are trying to minimize
            biggest_possible_remaining_wordcount = max([len(val) for val in temp_eval_to_words_map.values()])
            
            # if we found a new minimum
            if biggest_possible_remaining_wordcount < min_wordcount:
                min_wordcount = biggest_possible_remaining_wordcount
                chosen_word = word_to_guess
                
                # save current best wordlist map
                evaluation_to_wordlist_map = temp_eval_to_words_map

        # evaluate chosen word with answer
        enter_guess(chosen_word, keyboard)
        time.sleep(1)
        if classic_wordle:
            answer_evaluation = get_wordle_evaluation(chosen_word, game_rows[guess_number], browser)
            print(answer_evaluation)
            score.append(answer_evaluation)
        if answer_evaluation in evaluation_to_wordlist_map:
            narrowed_down_list = evaluation_to_wordlist_map[answer_evaluation]
            
        if answer_evaluation == [2, 2, 2, 2, 2]:
            score.append(answer_evaluation)
            return [chosen_word], score
        time.sleep(1)
        
        # once narrowed down to 1, we are done
        if len(narrowed_down_list) == 1:
            enter_guess(narrowed_down_list[0], keyboard)
            score.append([2, 2, 2, 2, 2])
            return [narrowed_down_list[0]], score
    return narrowed_down_list, score
            

def get_wordle_evaluation(chosen_word, game_row, browser):
    row = browser.execute_script('return arguments[0].shadowRoot', game_row)
    tiles = row.find_elements(By.CSS_SELECTOR, "game-tile")
    evaluation = []
    eval_to_int = {
        "correct": 2,
        "present": 1,
        "absent": 0
    }
    for tile in tiles:
        evaluation.append(eval_to_int[tile.get_attribute("evaluation")])
    return tuple(evaluation)

def get_wordmaster_evaluation(chosen_word, game_row, browser):
    evaluation = []
    for tile in game_row:
        if 'nm-inset-n-green' in tile.get_attribute("class"):
            evaluation.append(2)
        elif 'nm-inset-yellow-500' in tile.get_attribute("class"):
            evaluation.append(1)
        elif 'nm-inset-n-gray' in tile.get_attribute("class"):
            evaluation.append(0)
    return tuple(evaluation)
    
    
def enter_guess(word, keyboard):
    for letter in word:
        element = keyboard.get(letter)
        element.click()
        time.sleep(0.5)
    time.sleep(1)
    element = keyboard.get("↵")
    element.click()

def get_evaluation(answer, word):
    # 0 = nothing, 1 = yellow, 2 = green
    output = [0, 0, 0, 0, 0]
    
    # check for correct letter and placement
    for i in range(5):
        if word[i] == answer[i]:
            output[i] = 2
            answer = answer[:i] + ' ' + answer[i + 1:]
           
    # check for correct letter
    for i in range(5):
        char = word[i]
        if char in answer and output[i] == 0:
            output[i] = 1
            first_occurence = answer.find(char)
            answer = answer[:first_occurence] + ' ' + answer[first_occurence + 1:]
    return tuple(output)


def send_message_as_huey(message: str):
    GROUPME_API_URL = 'https://api.groupme.com/v3/bots/post'
    data = {
        'bot_id': os.getenv('GROUPME_BOT_ID'),
        'text':   message,
    }

    request = requests.post(url=GROUPME_API_URL, json=data)
    print(request.text)

def convert_score(score):
    message = "Wordle {}/6\n".format(len(score))
    green = '\U0001F7E9'
    yellow = '\U0001F7E8'
    black = '\u2B1B'
    for i in score:
        for letter in i:
            if letter == 0:
                message += black
            elif letter == 1:
                message += yellow
            elif letter == 2:
                message += green
        message += '\n'
    print(message)
    return message

def run_program(chrome):
    start_button = 'esc'
    classic_wordle = True

    
    # chrome_options.add_argument("--headless")
    # set up Selenium browser
    browser = chrome

    browser.get("https://www.nytimes.com/games/wordle/index.html")

    # wait to start the program
    time.sleep(2)

    # Close the popups
    try:
        browser.find_element(By.CSS_SELECTOR, '#pz-gdpr-btn-closex').click()
    except:
        pass
    try:
        instructions = browser.execute_script(
            "return document.querySelector('game-app').shadowRoot.querySelector('game-theme-manager').querySelector('game-modal').shadowRoot")
        gameicon = instructions.find_element(
            By.CLASS_NAME, 'close-icon')
        gameicon.click()
    except:
        pass
        
    # get game rows
    game_app = browser.find_element(By.TAG_NAME, 'game-app')
    board = browser.execute_script("return arguments[0].shadowRoot.getElementById('board')", game_app)
    game_rows = board.find_elements(By.TAG_NAME, 'game-row')

    keyboard = browser.execute_script(
        "return document.querySelector('game-app').shadowRoot.querySelector('game-theme-manager').querySelector('game-keyboard').shadowRoot.querySelector('#keyboard')")
    keyboard_rows = keyboard.find_elements(By.CLASS_NAME, 'row')
    keys = {}
    for row in keyboard_rows:
        for key in row.find_elements(By.XPATH, ('.//*')):
            keys[key.get_attribute('data-key')] = key
    
    answer, score = play(game_rows, browser, get_wordle_guesses(), get_wordle_answers(), keys, classic_wordle)
    print(answer)

    # share = browser.execute_script(
    #     "return document.querySelector('game-app').shadowRoot.querySelector('game-theme-manager').querySelector('game-modal').querySelector('game-stats').shadowRoot.querySelector('.container').querySelector('.footer').querySelector('.share').querySelector('button')")
    # browser.execute_script(
    #     'arguments[0].scrollIntoView({block: "center", inline: "center"})', share)
    # time.sleep(1)
    # share.click()
    # time.sleep(1)
    # score = pyperclip.paste()
    message = convert_score(score)
    send_message_as_huey(message)
    return answer


    
if __name__ == "__main__":
    handler()
