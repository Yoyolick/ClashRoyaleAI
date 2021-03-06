# A python program that attempts to play clash royale
# Ryan Zmuda 2021

import json
import random
import re
import time
from datetime import datetime

import cv2
import keyboard
import numpy as np
import pyautogui
import pytesseract as tess
import win32gui
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# for dev testing purposes
# probably just disable these later
verboseEnemyParse = False
verboseElixerParse = False
verboseDefStats = False
logicStateVerbose = True

# defualts
elixerStoreValue = 0
lastElixer = 1

# raidus of pixels to encompass text in recognition
elixerStoreScanRadius = 25
cardScanRadius = 15

# load our game coordinates from screenPoints.json (generated by configure.py)
with open("screenPoints.json") as json_file:
    # throw the json data into an object
    data = json.load(json_file)

    # screen origin coords
    screenOrigin = tuple(data["screenOrigin"])
    screenBotRight = tuple(data["screenBotRight"])

    # elixer store text position adjusted for screen origin converted to a tuple
    elixerStoreTextPos = (
        data["elixerTextCoords"][0] - screenOrigin[0],
        data["elixerTextCoords"][1] - screenOrigin[1],
    )

    # coords to click on cards to select them
    firstCardCoords = tuple(data["card1position"])
    secondCardCoords = tuple(data["card2position"])
    thirdCardCoords = tuple(data["card3position"])
    fourthCardCoords = tuple(data["card4position"])

    # emote coords
    emotePosition = tuple(data["emoteCoords"])
    emoteMenuPosition = tuple(data["emoteMenuCoords"])

    # lane bounds
    leftDefOrigin = tuple(data["leftDefOrigin"])
    leftDefOrigin2 = tuple(data["leftDefOrigin2"])

    rightDefOrigin = tuple(data["rightDefOrigin"])
    rightDefOrigin2 = tuple(data["rightDefOrigin2"])

    leftAttOrigin = tuple(data["leftAttOrigin"])
    leftAttOrigin2 = tuple(data["leftAttOrigin2"])

    rightAttOrigin = tuple(data["rightAttOrigin"])
    rightAttOrigin2 = tuple(data["rightAttOrigin2"])


# set our constants for our crop values so we dont have to compute them every frame
elixerCrop = (
    (elixerStoreTextPos[0] - elixerStoreScanRadius),
    (elixerStoreTextPos[1] - elixerStoreScanRadius),
    (elixerStoreTextPos[0] + elixerStoreScanRadius),
    (elixerStoreTextPos[1] + elixerStoreScanRadius),
)

# figure out our width and height of screen
screenSize = (screenBotRight[0] - screenOrigin[0], screenBotRight[1] - screenOrigin[1])

# set tesseract path
with open("tesseractPath.txt", "r") as tessPath:
    tess.pytesseract.tesseract_cmd = tessPath.read()


def screenshot(window_title=None):
    if window_title:
        hwnd = win32gui.FindWindow(None, window_title)
        if hwnd:
            win32gui.SetForegroundWindow(hwnd)
            x, y, x1, y1 = win32gui.GetClientRect(hwnd)
            x, y = win32gui.ClientToScreen(hwnd, (x, y))
            x1, y1 = win32gui.ClientToScreen(hwnd, (x1 - x, y1 - y))
            im = pyautogui.screenshot(region=(x, y, x1, y1))
            return im
        else:
            print("Window not found!")
    else:
        im = pyautogui.screenshot()
        return im


# get size of our current bluestacks window
im = screenshot("BlueStacks")
bluestacksSize = im.size

# calculate our crop amounts from our given playfield size and window size
cropTL = (0, bluestacksSize[1] - screenSize[1])
cropBR = (screenSize[0], bluestacksSize[1])

# constant crops for lane images (left, top, right, bottom)
leftDefCrop = (
    (leftDefOrigin[0] - screenOrigin[0]),
    (leftDefOrigin[1] - cropTL[1]),
    (leftDefOrigin2[0] - screenOrigin[0]),
    (leftDefOrigin2[1] - cropTL[1]),
)
rightDefCrop = (
    (rightDefOrigin[0] - screenOrigin[0]),
    (rightDefOrigin[1] - cropTL[1]),
    (rightDefOrigin2[0] - screenOrigin[0]),
    (rightDefOrigin2[1] - cropTL[1]),
)
leftAttCrop = (
    (leftAttOrigin[0] - screenOrigin[0]),
    (leftAttOrigin[1] - cropTL[1]),
    (leftAttOrigin2[0] - screenOrigin[0]),
    (leftAttOrigin2[1] - cropTL[1]),
)
rightAttCrop = (
    (rightAttOrigin[0] - screenOrigin[0]),
    (rightAttOrigin[1] - cropTL[1]),
    (rightAttOrigin2[0] - screenOrigin[0]),
    (rightAttOrigin2[1] - cropTL[1]),
)


def filterImage(img):
    # condensed filtering to grayscale binary image for easier recognition
    img = (
        img.convert("L")
        .filter(ImageFilter.MedianFilter())
        .point(lambda x: 0 if x < 220 else 255)
    )
    return img


def tessParse(im):
    # parse our text and
    detectedText = tess.image_to_string(im, lang="eng", config="--psm 6")

    detectedText = re.sub(
        "[^0-9]", "", detectedText
    )  # this is regex! wow im so god damn smart >:) totally didnt copy it from somewhere

    # return detected text corrected for recognition errors
    return detectedText


def parseStaticValues(
    elixerStoreValue,
    lastElixer,
):

    parseValuesElapsedTime = datetime.now()

    elixerStoreImg = im.crop((elixerCrop))
    # update current elixer store value based off playfield image
    elixerStoreImg = filterImage(elixerStoreImg)
    elixerStoreImg.save("images/elixerStore.png")
    # defualt to last known value if we dont know our current
    tmp = tessParse(elixerStoreImg)
    if tmp != "":
        elixerStoreValue = tmp

    if tmp == "0":
        tmp = lastElixer
        return tmp

    if verboseElixerParse:
        print("elixer store value:", elixerStoreValue)
        print(
            "elapsed elixer parse time:",
            datetime.now() - parseValuesElapsedTime,
        )

    lastElixer = elixerStoreValue
    return elixerStoreValue


# TODO this entire function needs refactoring
def detectEnemies(playfieldImage, query):
    # TODO if possible should crop after converting to np but im guessing you cant
    leftDefIm = playfieldImage.crop(leftDefCrop)
    rightDefIm = playfieldImage.crop(rightDefCrop)
    leftAttIm = playfieldImage.crop(leftAttCrop)
    rightAttIm = playfieldImage.crop(rightAttCrop)

    # TODO WIP ok basically cut up into lanes and shit and scan them
    # Load image
    leftDefIm = cv2.cvtColor(np.array(leftDefIm), cv2.COLOR_RGB2BGR)
    rightDefIm = cv2.cvtColor(np.array(rightDefIm), cv2.COLOR_RGB2BGR)
    leftAttIm = cv2.cvtColor(np.array(leftAttIm), cv2.COLOR_RGB2BGR)
    rightAttIm = cv2.cvtColor(np.array(rightAttIm), cv2.COLOR_RGB2BGR)

    # color defs - BGR order
    white = [255, 255, 255]
    black = [0, 0, 0]

    leftDefIm = np.where(
        np.all(leftDefIm == white, axis=-1, keepdims=True), white, black
    )
    rightDefIm = np.where(
        np.all(rightDefIm == white, axis=-1, keepdims=True), white, black
    )
    leftAttIm = np.where(
        np.all(leftAttIm == white, axis=-1, keepdims=True), white, black
    )
    rightAttIm = np.where(
        np.all(rightAttIm == white, axis=-1, keepdims=True), white, black
    )

    if query == "reference":
        # write all of our images (this is so inefficient lmao) TODO remove when not visualizing?
        cv2.imwrite("images/leftDefRef.png", leftDefIm)
        cv2.imwrite("images/leftAttRef.png", leftAttIm)
        cv2.imwrite("images/rightDefRef.png", rightDefIm)
        cv2.imwrite("images/rightAttRef.png", rightAttIm)
        return leftDefIm, leftAttIm, rightDefIm, rightAttIm
    else:
        # get the pixel differences between our two images for each lane attack def bound
        cv2.imwrite("images/leftDef.png", cv2.absdiff(leftDefRef, leftDefIm))
        cv2.imwrite("images/leftAtt.png", cv2.absdiff(leftAttRef, leftAttIm))
        cv2.imwrite("images/rightDef.png", cv2.absdiff(rightDefRef, rightDefIm))
        cv2.imwrite("images/rightAtt.png", cv2.absdiff(rightAttRef, rightAttIm))


# TODO WIP ok this part takes the data from detect enemies and makes the best decision, see notebook for logic
def parseEnemies():
    startTime = datetime.now()

    # lmao this is so inefficient TODO fix this shit
    leftAtt = cv2.imread("images/leftAtt.png")
    leftDef = cv2.imread("images/leftDef.png")
    rightAtt = cv2.imread("images/rightAtt.png")
    rightDef = cv2.imread("images/rightDef.png")

    # another block of pepega copy paste
    leftAtt = np.argwhere(leftAtt == 255)
    leftDef = np.argwhere(leftDef == 255)
    rightAtt = np.argwhere(rightAtt == 255)
    rightDef = np.argwhere(rightDef == 255)

    if verboseDefStats:
        print("left att", len(leftAtt))
        print("left def", len(leftDef))
        print("right att", len(rightAtt))
        print("right def", len(rightDef))

    leftAtt = len(leftAtt)
    leftDef = len(leftDef)
    rightAtt = len(rightAtt)
    rightDef = len(rightDef)

    # TODO this logic could always be done better
    if int(elixerStoreValue) >= 4:
        cardToPlace = random.randint(1, 4)
        if leftDef + leftAtt + rightAtt + rightDef >= 0:  # if there are enemies
            if (
                leftDef >= rightDef and leftDef + rightDef > leftAtt + rightAtt
            ):  # if more enemies are pushed up to defense on left and more enemies are attacking
                placeCard(cardToPlace, "leftDef")  # place units left def
            elif (
                rightDef >= leftDef and leftDef + rightDef > leftAtt + rightAtt
            ):  # more enemies right defense
                placeCard(cardToPlace, "rightDef")  # place units right def
            else:
                if (
                    True
                ):  # if the AI is targeting lane 0 TODO this is random to test shit
                    placeCard(cardToPlace, "leftAtt")  # place a unit in lane 0 home
                else:  # else AI is targeting lane 1
                    placeCard(cardToPlace, "rightAtt")  # place a unit in lane 1 home
        else:  # else there are no enemies
            if True:  # if the AI is targeting lane 0 TODO this is random to test shit
                placeCard(cardToPlace, "leftAtt")  # place a unit in lane 0 home
            else:  # else AI is targeting lane 1
                placeCard(cardToPlace, "rightAtt")  # place a unit in lane 1 home

    if verboseEnemyParse:
        print("elapsed enemy parse:", datetime.now() - startTime)


def emote():
    pyautogui.click(emoteMenuPosition[0], emoteMenuPosition[1])
    pyautogui.click(emotePosition[0], emotePosition[1])


# starting this index from 1 because its possibly faster (yes i know, barely if at all) {clarification: because it removes an addition operation}
def placeCard(cardNumber, position):
    elixerStoreValue = "1"
    # click on the card we want to use
    if cardNumber == 1:
        pyautogui.click(firstCardCoords[0], firstCardCoords[1])
    elif cardNumber == 2:
        pyautogui.click(secondCardCoords[0], secondCardCoords[1])
    elif cardNumber == 3:
        pyautogui.click(thirdCardCoords[0], thirdCardCoords[1])
    elif cardNumber == 4:
        pyautogui.click(fourthCardCoords[0], fourthCardCoords[1])

    # TODO why is this being declared every game loop, stupid ass
    defYOff = 1.5
    defXOff = 2
    attYOff = 2.5
    attXOff = 2

    # position placements, back full circle i guess lmao
    # TODO this should not be hardcoded, dumbass
    if position == "rightDef":
        if logicStateVerbose:
            print("DEBUG defending right")
        pyautogui.click(
            ((rightDefOrigin2[0] - rightDefOrigin[0]) / defXOff) + rightDefOrigin[0],
            ((rightDefOrigin2[1] - rightDefOrigin[1]) / defYOff) + rightDefOrigin[1],
        )
    elif position == "leftDef":
        if logicStateVerbose:
            print("DEBUG defending left")
        pyautogui.click(
            ((leftDefOrigin2[0] - leftDefOrigin[0]) / defXOff) + leftDefOrigin[0],
            ((leftDefOrigin2[1] - leftDefOrigin[1]) / defYOff) + leftDefOrigin[1],
        )
    elif position == "rightAtt":
        if logicStateVerbose:
            print("DEBUG attacking right")
        pyautogui.click(
            ((rightAttOrigin2[0] - rightAttOrigin[0]) / attXOff) + rightAttOrigin[0],
            ((rightAttOrigin2[1] - rightAttOrigin[1]) / attYOff) + rightAttOrigin[1],
        )
    elif position == "leftAtt":
        if logicStateVerbose:
            print("DEBUG attacking left")
        pyautogui.click(
            ((leftAttOrigin2[0] - leftAttOrigin[0]) / attXOff) + leftAttOrigin[0],
            ((leftAttOrigin2[1] - leftAttOrigin[1]) / attYOff) + leftAttOrigin[1],
        )


if __name__ == "__main__":

    # TODO REMOVE FIRST BINDABLE FLOW TAKE SCREENSHOT ONE FRAME
    # idk what i mean by this comment but do this better have a first run function maybe
    im = screenshot("BlueStacks")
    # crop by our playfield bounds in relation to the bluestacks window
    im = im.crop(
        (
            cropTL[0],
            cropTL[1],
            cropBR[0],
            cropBR[1],
        )
    )
    # get our reference images one time
    leftDefRef = detectEnemies(im, "reference")[0]
    leftAttRef = detectEnemies(im, "reference")[1]
    rightDefRef = detectEnemies(im, "reference")[2]
    rightAttRef = detectEnemies(im, "reference")[3]

    # TODO temp targeted lane (this should be dynamic in the future)
    targetedLane = random.randint(0, 1)
    if logicStateVerbose:
        print("DEBUG Targeting lane", targetedLane)

    while True:

        # get a screenshot of the playfield
        im = screenshot("BlueStacks")
        # crop by our playfield bounds in relation to the bluestacks window
        im = im.crop(
            (
                cropTL[0],
                cropTL[1],
                cropBR[0],
                cropBR[1],
            )
        )

        # parse playfield for elixer store
        elixerStoreValue = parseStaticValues(elixerStoreValue, lastElixer)

        # check lanes for enemies
        detectEnemies(im, "normal")

        # use logic to determine threats and placement
        parseEnemies()

        # emote()  # TODO incorporate emotes into some fashion

        # emergency abort
        if keyboard.is_pressed("q"):
            print("-> EMERGENCY EXIT")
            exit()

# HIGH PRIO:
# TODO placement points need work
# TODO elixer detection FIX NOW

# LOW PRIO:
# TODO AI check for taken towers to advance units faster
# TODO visualization mode for when you want to show off the AI working and another mode to toggle off the visuals for preformance (basically enables/disables image saving)
# TODO naming convention if you can be fucked to fix it
# TODO its possible emotes will show up in the zones that are being monitored, look into that
# TODO organize constants and first declares
# TODO python asynch announce its decisions
# TODO honestly this whole thing should be in a class to use self variable what are you doing dumbass
