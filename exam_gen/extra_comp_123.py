# -*- coding: utf-8 -*-
"""Round 12 Year 1-3 comprehension blocks (Part 4).  The built-in bank has
only 3/2/2 blocks for years 1/2/3, so papers repeated.  Template blocks here
expand into 18 passage/q sets per year via story-level placeholders, merging
with the built-ins to give >= 20 distinct sets a year.

Every variant keeps the same grammar and answers, so all questions stay
answerable; distractors are static and never collide with the answer.
"""


def _mk(title, passage, qs, variants):
    out = []
    for v in variants:
        p = passage
        qs2 = [dict(q) for q in qs]
        for key, val in v.items():
            tok = "{" + key + "}"
            p = p.replace(tok, val)
            for q in qs2:
                q["stem"] = q["stem"].replace(tok, val)
                q["opts"] = [o.replace(tok, val) for o in q["opts"]]
        out.append({"title": title, "passage": p, "qs": qs2})
    return out


COMPREHENSION = {}

# ---------------------------------------------------------------- Year 1 ---
GIRL = ["Mei Lin", "Siti", "Devi", "Aina", "Wan Ying", "Maya"]
BOY = ["Ali", "Wei Jie", "Ravi", "Arif", "Jia Qi", "Kumar"]
DAY = ["Saturday", "Sunday", "Monday", "Friday", "Tuesday", "Thursday"]

COMPREHENSION[1] = (
    _mk(
        "At the Park",
        "{name} goes to the park with her mother on a sunny day. She plays "
        "on the swing and slides down the slide. Then she feeds the ducks in "
        "the pond. After that, they sit under a tree and eat ice cream "
        "together. The park is very clean and quiet.",
        [
            {"stem": "Where does {name} play?", "opts": ["at the park", "in the kitchen", "on the bus"], "ans": 0},
            {"stem": "Who goes to the park with {name}?", "opts": ["her mother", "her teacher", "a nurse"], "ans": 0},
            {"stem": "What does {name} feed in the pond?", "opts": ["the ducks", "the cats", "the birds"], "ans": 0},
            {"stem": "What do they eat under the tree?", "opts": ["ice cream", "noodles", "pancakes"], "ans": 0},
            {"stem": "How is the park?", "opts": ["clean and quiet", "dark and noisy", "big and cold"], "ans": 0},
        ],
        [{"name": G} for G in GIRL]) +
    _mk(
        "My Best Friend",
        "{name} has a best friend called Nora. Nora is tall and has long "
        "black hair. They sit next to each other in class. At recess, they "
        "share food and play in the field. On Saturdays, they ride their "
        "bicycles to the supermarket. {name} is happy to have Nora as a "
        "friend.",
        [
            {"stem": "Who is {name}'s best friend?", "opts": ["Nora", "Mimi", "Aunty Lin"], "ans": 0},
            {"stem": "What does Nora look like?", "opts": ["tall with long hair", "short with curly hair", "thin with glasses"], "ans": 0},
            {"stem": "What do they do at recess?", "opts": ["share food and play", "do homework", "sleep"], "ans": 0},
            {"stem": "Where do they ride to on Saturdays?", "opts": ["the supermarket", "the school", "the beach"], "ans": 0},
            {"stem": "How does {name} feel about having Nora?", "opts": ["happy", "sad", "angry"], "ans": 0},
        ],
        [{"name": G} for G in GIRL]) +
    _mk(
        "The Helpful Boy",
        "{name} is a helpful boy. After school, he helps his mother in the "
        "kitchen. He washes the vegetables and feeds his little cat. Then he "
        "sweeps the floor with a broom. His mother says, 'Thank you, my good "
        "boy.' {name} feels very proud and happy.",
        [
            {"stem": "Where does {name} help his mother?", "opts": ["in the kitchen", "in the park", "at the shop"], "ans": 0},
            {"stem": "What does {name} feed?", "opts": ["his little cat", "a big dog", "some fish"], "ans": 0},
            {"stem": "How does {name} sweep the floor?", "opts": ["with a broom", "with his hands", "with a cloth"], "ans": 0},
            {"stem": "What does his mother say?", "opts": ["Thank you", "Good night", "Hurry up"], "ans": 0},
            {"stem": "How does {name} feel at the end?", "opts": ["proud and happy", "tired and hungry", "sad and bored"], "ans": 0},
        ],
        [{"name": B} for B in BOY])
)

# ---------------------------------------------------------------- Year 2 ---
COMPREHENSION[2] = (
    _mk(
        "Canteen Day",
        "On {day}, {name} and her friends have a canteen day at school. "
        "Every pupil brings some food from home. {name} brings curry and "
        "rice. Kok Ming brings a big cake. Mei Li brings drinks and "
        "cupcakes. All the food is sold to raise money for the school library. "
        "The pupils enjoy the food and laugh together.",
        [
            {"stem": "When is the canteen day?", "opts": ["on {day}", "on a rainy day", "at night"], "ans": 0},
            {"stem": "What does {name} bring?", "opts": ["curry and rice", "a big cake", "drinks"], "ans": 0},
            {"stem": "Who brings a big cake?", "opts": ["Kok Ming", "{name}", "Mei Li"], "ans": 0},
            {"stem": "Why do the pupils sell the food?", "opts": ["to help the library", "to buy toys", "to go on a trip"], "ans": 0},
            {"stem": "How do the pupils enjoy the day?", "opts": ["they eat and laugh together", "they sleep all day", "they watch television"], "ans": 0},
        ],
        [{"name": G, "day": D} for G, D in zip(GIRL, DAY)]) +
    _mk(
        "A Visit to Grandfather",
        "{name} visits his grandfather in the kampung on {day}. Grandfather "
        "has a big orchard with durian, rambutan and mango trees. He lets "
        "{name} climb a small tree to pick rambutan. Grandmother cooks a "
        "tasty chicken curry in the kitchen. In the evening, they sit on the "
        "veranda and listen to Grandfather's old stories.",
        [
            {"stem": "Who does {name} visit?", "opts": ["his grandfather", "his teacher", "a farmer"], "ans": 0},
            {"stem": "What fruit grows in the orchard?", "opts": ["durian, rambutan and mango", "apples and pears", "grapes and oranges"], "ans": 0},
            {"stem": "What does {name} pick?", "opts": ["rambutan", "coffee beans", "flowers"], "ans": 0},
            {"stem": "What does Grandmother cook?", "opts": ["chicken curry", "fried noodles", "fish soup"], "ans": 0},
            {"stem": "What do they do in the evening?", "opts": ["listen to old stories", "go fishing", "watch a film"], "ans": 0},
        ],
        [{"name": B, "day": D} for B, D in zip(BOY, DAY)]) +
    _mk(
        "Rainy Day at Home",
        "One rainy day, {name} cannot play outside. She decides to build a "
        "castle with her blocks. Then she draws a picture of a rainbow and "
        "pastes it on the fridge. In the afternoon, she helps her mother bake "
        "butter biscuits. Her little brother counts the biscuits while she "
        "sings a song. The family reads together before bedtime.",
        [
            {"stem": "Why cannot {name} play outside?", "opts": ["because it is rainy", "because it is dark", "because she is ill"], "ans": 0},
            {"stem": "What does she build with her blocks?", "opts": ["a castle", "a bridge", "a robot"], "ans": 0},
            {"stem": "Where does she paste her drawing?", "opts": ["on the fridge", "on the door", "on the window"], "ans": 0},
            {"stem": "What do they bake together?", "opts": ["butter biscuits", "banana cakes", "cheese tarts"], "ans": 0},
            {"stem": "What does the family do before bedtime?", "opts": ["read together", "watch television", "sing loudly"], "ans": 0},
        ],
        [{"name": G} for G in GIRL])
)

# ---------------------------------------------------------------- Year 3 ---
FEST = ["Hari Raya Aidilfitri", "Chinese New Year", "Deepavali",
        "Hari Gawai", "Hari Merdeka", "Christmas"]

COMPREHENSION[3] = (
    _mk(
        "Sports Day",
        "On Saturday, the pupils of SK Taman Murni hold their Sports Day. "
        "{name} takes part in the relay race and runs very fast. Her friend "
        "Nurul jumps high in the long jump. In the tug-of-war, the Blue Team "
        "pulls hard and wins the match. Parents cheer loudly from the "
        "grandstand and take many pictures of the winners.",
        [
            {"stem": "Where is the Sports Day held?", "opts": ["at SK Taman Murni", "at the swimming pool", "in the library"], "ans": 0},
            {"stem": "What race does {name} take part in?", "opts": ["the relay race", "the long jump", "the tug-of-war"], "ans": 0},
            {"stem": "Who jumps high in the long jump?", "opts": ["Nurul", "{name}", "the coach"], "ans": 0},
            {"stem": "Which team wins the tug-of-war?", "opts": ["the Blue Team", "the Red Team", "the Green Team"], "ans": 0},
            {"stem": "What do the parents do from the grandstand?", "opts": ["cheer and take pictures", "sleep and eat", "run and jump"], "ans": 0},
        ],
        [{"name": G} for G in GIRL]) +
    _mk(
        "The Smart Parrot",
        "A kind old man keeps a smart parrot named {bird}. {bird} can say "
        "'Welcome home' and 'Time for lunch' to the old man. One evening, the old man "
        "forgets his {item} at the {place}. When a stranger tries to enter "
        "the house, {bird} shouts loudly to call the neighbours. The "
        "neighbours catch the stranger and return the {item}. The old man "
        "thanks his clever bird.",
        [
            {"stem": "What is the name of the parrot?", "opts": ["{bird}", "Milo", "Koko"], "ans": 0},
            {"stem": "What does {bird} say when the man comes home?", "opts": ["Welcome home", "Time to sleep", "Open the gate"], "ans": 0},
            {"stem": "Where does the old man forget his {item}?", "opts": ["at the {place}", "at the park", "in the bus"], "ans": 0},
            {"stem": "Why does {bird} shout loudly?", "opts": ["to call the neighbours", "to sing a song", "to scare the cat"], "ans": 0},
            {"stem": "What do the neighbours return to the old man?", "opts": ["his {item}", "his food", "the cage"], "ans": 0},
        ],
        [{"bird": B, "item": I, "place": P}
         for B, I, P in zip(["Kimi", "Poko", "Momo", "Lili", "Dino", "Bibi"],
                            ["wallet"] * 3 + ["keys"] * 3,
                            ["market", "bus stop", "shop"] * 2)]) +
    _mk(
        "Festival Preparations",
        "The {fest} holiday is coming soon. {name} and her mother go to the "
        "shopping mall to buy new clothes and decorations. Father hangs "
        "colourful lanterns in front of the house. Grandmother bakes her "
        "famous cookies in the kitchen. On the night before the festival, the "
        "whole family gathers to clean the house and set the table for the "
        "big celebration dinner.",
        [
            {"stem": "Which holiday is coming soon?", "opts": ["{fest}", "New Year Eve party", "a school exam"], "ans": 0},
            {"stem": "Who goes shopping with {name}?", "opts": ["her mother", "her father", "her grandmother"], "ans": 0},
            {"stem": "What does father hang in front of the house?", "opts": ["lanterns", "curtains", "balloons"], "ans": 0},
            {"stem": "What does grandmother bake?", "opts": ["cookies", "bread", "noodles"], "ans": 0},
            {"stem": "What does the family do the night before?", "opts": ["clean the house and set the table", "go to the beach", "watch cartoons"], "ans": 0},
        ],
        [{"name": G, "fest": F} for G, F in zip(GIRL, FEST)])
)