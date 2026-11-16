# -*- coding: utf-8 -*-
"""DSKP-grounded Part 5 word boxes for Years 1-3.

Round 25.  The pre-Round-25 Part 5 pool was freehand: a Year 3 word box
offered ``civet, gecko, tapir, orangutan, hornbill`` with a clue like *"this
night animal helps make a famous coffee from the islands"*.  Nothing in the
project tied a word box to the curriculum, so the pools drifted into trivia a
Year 3 pupil has no way of having met.

Every target word below is on the KSSR Semakan 2017 DSKP list for its year
(see :mod:`exam_gen.dskp_words`), and every distractor is either another word
from the same list or a closed-set everyday word, so a pupil can reject the
wrong options on meaning rather than on guesswork.

The item shape matches the existing pools: a ``box`` of five words printed
above the questions, then one MCQ per word whose clue describes it.
``tests/run_tests.py::TestDskpGate`` fails the build if a word here ever
drifts off the list.
"""

WORDS_DSKP = {}

# ---------------------------------------------------------------- Year 1 ---
# A1 low: pets and animals, classroom objects, family, food, colours.
# Clues stay in the present simple and name no year-3+ concept.
WORDS_DSKP[1] = [
    {"box": ["cat", "dog", "bird", "fish", "frog"],
     "items": [
         {"stem": "My pet has soft fur and says 'meow'. It is a __________.",
          "opts": ["cat", "dog", "duck"], "ans": 0, "ans_text": "cat"},
         {"stem": "This animal barks loudly and wags its long tail. It is a "
                  "__________.",
          "opts": ["dog", "cat", "fish"], "ans": 0, "ans_text": "dog"},
         {"stem": "It has colourful feathers and sings in the tree. It is a "
                  "__________.",
          "opts": ["bird", "frog", "horse"], "ans": 0, "ans_text": "bird"},
         {"stem": "This animal lives in water and swims with its fins. It is "
                  "a __________.",
          "opts": ["fish", "cat", "mouse"], "ans": 0, "ans_text": "fish"},
         {"stem": "This little animal hops and jumps near the pond. It is a "
                  "__________.",
          "opts": ["frog", "dog", "snake"], "ans": 0, "ans_text": "frog"},
     ]},
    {"box": ["bag", "book", "pencil", "ruler", "crayon"],
     "items": [
         {"stem": "I carry my books and my lunch in this. It is a __________.",
          "opts": ["bag", "book", "pencil"], "ans": 0, "ans_text": "bag"},
         {"stem": "I open this to read a story. It is a __________.",
          "opts": ["book", "bag", "crayon"], "ans": 0, "ans_text": "book"},
         {"stem": "I write my name with this. It is a __________.",
          "opts": ["pencil", "ruler", "bag"], "ans": 0, "ans_text": "pencil"},
         {"stem": "I use this to draw a straight line. It is a __________.",
          "opts": ["ruler", "book", "crayon"], "ans": 0, "ans_text": "ruler"},
         {"stem": "I colour my picture with this. It is a __________.",
          "opts": ["crayon", "bag", "book"], "ans": 0, "ans_text": "crayon"},
     ]},
    {"box": ["mother", "father", "sister", "brother", "baby"],
     "items": [
         {"stem": "She is my mother's mother. She is my __________.",
          "opts": ["grandmother", "sister", "baby"], "ans": 0,
          "ans_text": "grandmother"},
         {"stem": "He is my father's father. He is my __________.",
          "opts": ["grandfather", "brother", "baby"], "ans": 0,
          "ans_text": "grandfather"},
         {"stem": "This little child drinks milk from a bottle. It is a "
                  "__________.",
          "opts": ["baby", "friend", "boy"], "ans": 0, "ans_text": "baby"},
         {"stem": "He is my mother's brother. He is my __________.",
          "opts": ["uncle", "sister", "grandfather"], "ans": 0,
          "ans_text": "uncle"},
         {"stem": "She is my aunt's daughter. She is my __________.",
          "opts": ["cousin", "uncle", "baby"], "ans": 0, "ans_text": "cousin"},
     ]},
    {"box": ["apple", "banana", "cake", "milk", "water"],
     "items": [
         {"stem": "This fruit is red and it grows on a tree. It is an "
                  "__________.",
          "opts": ["apple", "banana", "cake"], "ans": 0, "ans_text": "apple"},
         {"stem": "This fruit is long and yellow. We peel it. It is a "
                  "__________.",
          "opts": ["banana", "apple", "milk"], "ans": 0, "ans_text": "banana"},
         {"stem": "This is sweet and we eat it on our birthday. It is a "
                  "__________.",
          "opts": ["cake", "water", "banana"], "ans": 0, "ans_text": "cake"},
         {"stem": "This drink is white and comes from a cow. It is __________.",
          "opts": ["milk", "apple", "cake"], "ans": 0, "ans_text": "milk"},
         {"stem": "I am thirsty. I drink this every day. It is __________.",
          "opts": ["water", "cake", "banana"], "ans": 0, "ans_text": "water"},
     ]},
    {"box": ["red", "blue", "green", "yellow", "black"],
     "items": [
         {"stem": "The apple on my plate is the colour of blood. It is "
                  "__________.",
          "opts": ["red", "blue", "green"], "ans": 0, "ans_text": "red"},
         {"stem": "The sky is this colour on a clear day. It is __________.",
          "opts": ["blue", "black", "red"], "ans": 0, "ans_text": "blue"},
         {"stem": "The leaves on the tree are this colour. It is __________.",
          "opts": ["green", "yellow", "black"], "ans": 0, "ans_text": "green"},
         {"stem": "The lemon and the sun are this colour. It is __________.",
          "opts": ["yellow", "red", "blue"], "ans": 0, "ans_text": "yellow"},
         {"stem": "The night sky is this colour when there is no moon. It is "
                  "__________.",
          "opts": ["black", "green", "yellow"], "ans": 0, "ans_text": "black"},
     ]},
]

# ---------------------------------------------------------------- Year 2 ---
# A1 low: body parts, clothes, rooms of the house, nature, toys.
WORDS_DSKP[2] = [
    {"box": ["kitchen", "bathroom", "bedroom", "garden", "door"],
     "items": [
         {"stem": "Mum cooks our lunch in this room. It is the __________.",
          "opts": ["kitchen", "bathroom", "bedroom"], "ans": 0,
          "ans_text": "kitchen"},
         {"stem": "I wash my hands and take a bath in this room. It is the "
                  "__________.",
          "opts": ["bathroom", "kitchen", "garden"], "ans": 0,
          "ans_text": "bathroom"},
         {"stem": "I sleep in this room at night. It is the __________.",
          "opts": ["bedroom", "kitchen", "garden"], "ans": 0,
          "ans_text": "bedroom"},
         {"stem": "My mother grows flowers behind the house. It is the "
                  "__________.",
          "opts": ["garden", "bathroom", "kitchen"], "ans": 0,
          "ans_text": "garden"},
         {"stem": "We open this to walk into the house. It is the __________.",
          "opts": ["door", "window", "bed"], "ans": 0, "ans_text": "door"},
     ]},
    {"box": ["hat", "shirt", "skirt", "shoes", "socks"],
     "items": [
         {"stem": "I wear this on my head when the sun is hot. It is a "
                  "__________.",
          "opts": ["hat", "shirt", "shoes"], "ans": 0, "ans_text": "hat"},
         {"stem": "I wear this on my body. It has sleeves. It is a __________.",
          "opts": ["shirt", "skirt", "socks"], "ans": 0, "ans_text": "shirt"},
         {"stem": "My sister wears this below her waist. It is a __________.",
          "opts": ["skirt", "hat", "shirt"], "ans": 0, "ans_text": "skirt"},
         {"stem": "I wear these on my feet when I walk to school. They are "
                  "__________.",
          "opts": ["shoes", "socks", "hat"], "ans": 0, "ans_text": "shoes"},
         {"stem": "I wear these on my feet inside my shoes. They are "
                  "__________.",
          "opts": ["socks", "skirt", "hat"], "ans": 0, "ans_text": "socks"},
     ]},
    {"box": ["head", "hands", "eyes", "ears", "nose"],
     "items": [
         {"stem": "I see with these two. They are my __________.",
          "opts": ["eyes", "ears", "nose"], "ans": 0, "ans_text": "eyes"},
         {"stem": "I hear with these two. They are my __________.",
          "opts": ["ears", "eyes", "hands"], "ans": 0, "ans_text": "ears"},
         {"stem": "I smell with this one. It is my __________.",
          "opts": ["nose", "eyes", "ears"], "ans": 0, "ans_text": "nose"},
         {"stem": "I hold my book with these two. They are my __________.",
          "opts": ["hands", "eyes", "nose"], "ans": 0, "ans_text": "hands"},
         {"stem": "My hat sits on this. It is my __________.",
          "opts": ["head", "hands", "eyes"], "ans": 0, "ans_text": "head"},
     ]},
    {"box": ["sun", "rain", "wind", "tree", "flower"],
     "items": [
         # the answer must not also appear in the clue, or the pupil can
          # read it off the stem instead of choosing
          {"stem": "It is hot in the afternoon and I always wear a hat. "
                  "It is the __________.",
          "opts": ["sun", "rain", "wind"], "ans": 0, "ans_text": "sun"},
         {"stem": "The water falls from the sky and we use an umbrella. It "
                  "is __________.",
          "opts": ["rain", "sun", "tree"], "ans": 0, "ans_text": "rain"},
         {"stem": "The air moves and my kite flies high. It is the __________.",
          "opts": ["wind", "rain", "sun"], "ans": 0, "ans_text": "wind"},
         {"stem": "It is very tall and it has a trunk. It is a __________.",
          "opts": ["tree", "flower", "wind"], "ans": 0, "ans_text": "tree"},
         {"stem": "It is small and it grows in my mother's garden. It is a "
                  "__________.",
          "opts": ["flower", "tree", "sun"], "ans": 0, "ans_text": "flower"},
     ]},
    {"box": ["ball", "doll", "kite", "train", "camera"],
     "items": [
         {"stem": "I kick it with my foot in the field. It is a __________.",
          "opts": ["ball", "doll", "kite"], "ans": 0, "ans_text": "ball"},
         {"stem": "This has a soft body and a dress. I play house with it. "
                  "It is a __________.",
          "opts": ["doll", "ball", "train"], "ans": 0, "ans_text": "doll"},
         {"stem": "It flies in the sky when the wind blows. It is a "
                  "__________.",
          "opts": ["kite", "doll", "ball"], "ans": 0, "ans_text": "kite"},
         {"stem": "It runs on the track and it pulls carriages. It is a "
                  "__________.",
          "opts": ["train", "kite", "doll"], "ans": 0, "ans_text": "train"},
         {"stem": "I use it to take a photo of my family. It is a __________.",
          "opts": ["camera", "ball", "train"], "ans": 0, "ans_text": "camera"},
     ]},
]

# ---------------------------------------------------------------- Year 3 ---
# A1 mid: places in town, occupations, transport, food, time words.
# The occupations box reproduces the official Year 3 Part 5 word box.
WORDS_DSKP[3] = [
    {"box": ["pilot", "dentist", "firefighter", "nurse", "chef"],
     "items": [
         {"stem": "He flies aeroplanes across the sky. He is a __________.",
          "opts": ["dentist", "firefighter", "pilot"], "ans": 2,
          "ans_text": "pilot"},
         {"stem": "He pulls out bad teeth and checks our gums. He is a "
                  "__________.",
          "opts": ["dentist", "nurse", "pilot"], "ans": 0,
          "ans_text": "dentist"},
         {"stem": "He puts out fires and rescues people. He is a __________.",
          "opts": ["firefighter", "dentist", "nurse"], "ans": 0,
          "ans_text": "firefighter"},
         {"stem": "She helps the doctor and takes care of the sick. She is a "
                  "__________.",
          "opts": ["dentist", "nurse", "pilot"], "ans": 1, "ans_text": "nurse"},
         {"stem": "He cooks delicious food in the restaurant kitchen. He is a "
                  "__________.",
          "opts": ["chef", "nurse", "pilot"], "ans": 0, "ans_text": "chef"},
     ]},
    {"box": ["school", "hospital", "library", "zoo", "cafe"],
     "items": [
         {"stem": "My brother goes here every day to learn and to meet his "
                  "friends. It is the __________.",
          "opts": ["school", "hospital", "zoo"], "ans": 0, "ans_text": "school"},
         {"stem": "My aunt works here and she helps sick people. It is the "
                  "__________.",
          "opts": ["hospital", "school", "cafe"], "ans": 0,
          "ans_text": "hospital"},
         {"stem": "I go here to borrow books and to read quietly. It is the "
                  "__________.",
          "opts": ["library", "zoo", "hospital"], "ans": 0,
          "ans_text": "library"},
         {"stem": "We saw the tiger and the elephant here on Sunday. It is "
                  "the __________.",
          "opts": ["zoo", "library", "school"], "ans": 0, "ans_text": "zoo"},
         {"stem": "We sit here and my father buys a hot drink. It is the "
                  "__________.",
          "opts": ["cafe", "zoo", "library"], "ans": 0, "ans_text": "cafe"},
     ]},
    {"box": ["bus", "train", "boat", "bicycle", "plane"],
     "items": [
         {"stem": "Many pupils ride in this every morning. It is a "
                  "__________.",
          "opts": ["bus", "train", "boat"], "ans": 0, "ans_text": "bus"},
         {"stem": "It runs on the track and it stops at the station. It is a "
                  "__________.",
          "opts": ["train", "bus", "bicycle"], "ans": 0, "ans_text": "train"},
         {"stem": "My uncle uses this on the sea to go from one island to "
                  "another. It is a __________.",
          "opts": ["boat", "bus", "train"], "ans": 0, "ans_text": "boat"},
         {"stem": "It has two wheels and my sister rides it to school. It is "
                  "a __________.",
          "opts": ["bicycle", "boat", "plane"], "ans": 0,
          "ans_text": "bicycle"},
         {"stem": "It has wings and it flies above the clouds. It is a "
                  "__________.",
          "opts": ["plane", "boat", "bus"], "ans": 0, "ans_text": "plane"},
     ]},
    {"box": ["rice", "noodles", "bread", "soup", "tea"],
     "items": [
         {"stem": "We eat this with curry at lunch. It is __________.",
          "opts": ["rice", "bread", "tea"], "ans": 0, "ans_text": "rice"},
         {"stem": "This is long and thin. My mother cooks it in hot water. "
                  "It is __________.",
          "opts": ["noodles", "rice", "bread"], "ans": 0,
          "ans_text": "noodles"},
         {"stem": "This is made from flour and we toast it for breakfast. It "
                  "is __________.",
          "opts": ["bread", "rice", "soup"], "ans": 0, "ans_text": "bread"},
         {"stem": "This is hot and I drink it from a bowl with a spoon. It is "
                  "__________.",
          "opts": ["soup", "bread", "tea"], "ans": 0, "ans_text": "soup"},
         {"stem": "My grandmother pours this into a cup for me every morning. "
                  "It is __________.",
          "opts": ["tea", "soup", "rice"], "ans": 0, "ans_text": "tea"},
     ]},
    {"box": ["morning", "afternoon", "evening", "night", "today"],
     "items": [
         {"stem": "I brush my teeth and eat breakfast at this time. It is "
                  "__________.",
          "opts": ["morning", "evening", "night"], "ans": 0,
          "ans_text": "morning"},
         {"stem": "We have our lessons at this time, after lunch. It is the "
                  "__________.",
          "opts": ["afternoon", "morning", "evening"], "ans": 0,
          "ans_text": "afternoon"},
         {"stem": "My father comes home from work at this time. It is "
                  "__________.",
          "opts": ["evening", "morning", "afternoon"], "ans": 0,
          "ans_text": "evening"},
         {"stem": "I sleep at this time, when it is dark outside. It is "
                  "__________.",
          "opts": ["night", "morning", "afternoon"], "ans": 0,
          "ans_text": "night"},
         {"stem": "It is the day I am writing this story. It is __________.",
          "opts": ["today", "night", "morning"], "ans": 0, "ans_text": "today"},
     ]},
]
