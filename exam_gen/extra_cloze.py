# -*- coding: utf-8 -*-
"""Round 12 cloze passages (Part 2, 4 gaps each).  The bank ships only ~2
blocks a year, which made papers repeat.  Template blocks here expand into
18 distinct passages per year (merged with the built-in 2 => 20/year).

Each template has story-level placeholders ({name}, {day}, {place} ...) that
swap to produce genuinely different mini-stories; the four gap answers stay
fixed per template so every variant stays grammatical and answerable.
"""


def _mk(passage, gaps, variants):
    """Expand one template's variant dicts into full blocks (no raw base)."""
    out = []
    for v in variants:
        p, gs = passage, [dict(g) for g in gaps]
        for key, val in v.items():
            tok = "{" + key + "}"
            p = p.replace(tok, val)
            for g in gs:
                g["stem"] = g["stem"].replace(tok, val)
                g["opts"] = [o.replace(tok, val) for o in g["opts"]]
        out.append({"passage": p, "gaps": gs})
    return out


DAY = ["Saturday", "Sunday", "Monday", "Friday", "Tuesday", "Thursday"]
GIRL = ["Mei Lin", "Siti", "Devi", "Aina", "Wan Ying", "Maya"]
BOY = ["Ali", "Wei Jie", "Ravi", "Arif", "Jia Qi", "Kumar"]

CLOZE = {}

# ---------------------------------------------------------------- Year 1 ---
CLOZE[1] = (
    _mk(
        "Early in the morning, {day} is sunny. {name} wakes up and puts on "
        "his school (6)_______. He eats two slices of bread and drinks a cup "
        "of (7)_______. Then he rides his (8)_______ to the park. He meets "
        "his (9)_______ there and they play together.",
        [
            {"stem": "{name} puts on his school __________.",
             "opts": ["uniform", "bed", "plate"], "ans": 0},
            {"stem": "He drinks a cup of __________.",
             "opts": ["milk", "soup", "salt"], "ans": 0},
            {"stem": "He rides his __________ to the park.",
             "opts": ["bicycle", "kite", "boat"], "ans": 0},
            {"stem": "He meets his __________ in the park.",
             "opts": ["friends", "books", "shoes"], "ans": 0},
        ],
        [{"name": B, "day": D} for B, D in zip(BOY, DAY[:6])]) +
    _mk(
        "It is a hot {day}. {name} goes to the market with his mother. His "
        "mother buys fish and (6)_______ for dinner. {name} likes to eat "
        "(7)_______ with rice. After that, they buy a big (8)_______ for "
        "grandmother. They go home by (9)_______.",
        [
            {"stem": "His mother buys fish and __________ for dinner.",
             "opts": ["vegetables", "pencils", "balloons"], "ans": 0},
            {"stem": "{name} likes to eat __________ with rice.",
             "opts": ["fried chicken", "ice candy", "sweets"], "ans": 0},
            {"stem": "They buy a big __________ for grandmother.",
             "opts": ["watermelon", "stone", "bottle"], "ans": 0},
            {"stem": "They go home by __________.",
             "opts": ["bus", "boat", "plane"], "ans": 0},
        ],
        [{"name": B, "day": D} for B, D in zip(BOY[1:] + BOY[:1], DAY)]) +
    _mk(
        "In the evening, {name} helps his mother. He waters the plants in "
        "the (6)_______ and feeds the (7)_______. His sister sweeps the "
        "(8)_______. Then they watch cartoons on the (9)_______ together.",
        [
            {"stem": "He waters the plants in the __________.",
             "opts": ["garden", "bathroom", "kitchen"], "ans": 0},
            {"stem": "He feeds the __________.",
             "opts": ["cat", "book", "shirt"], "ans": 0},
            {"stem": "His sister sweeps the __________.",
             "opts": ["floor", "ceiling", "window"], "ans": 0},
            {"stem": "They watch cartoons on the __________.",
             "opts": ["television", "blackboard", "fan"], "ans": 0},
        ],
        [{"name": B} for B in BOY])
)

# ---------------------------------------------------------------- Year 2 ---
CLOZE[2] = (
    _mk(
        "On {day}, {name} and his friends have a gotong-royong. They pick up "
        "(6)_______ in the field and sweep the school (7)_______. Wei Jie "
        "waters the plants in the (8)_______. The pupils are happy to see the "
        "clean school. They rest and eat (9)_______ together.",
        [
            {"stem": "They pick up __________ in the field.",
             "opts": ["rubbish", "toys", "flowers"], "ans": 0},
            {"stem": "They sweep the school __________.",
             "opts": ["hall", "pool", "roof"], "ans": 0},
            {"stem": "Wei Jie waters the plants in the __________.",
             "opts": ["garden", "canteen", "toilet"], "ans": 0},
            {"stem": "They eat __________ together after that.",
             "opts": ["noodles", "chalk", "paper"], "ans": 0},
        ],
        [{"name": B, "day": D} for B, D in zip(BOY, DAY)]) +
    _mk(
        "During {festival}, {name} is very happy. Grandmother gives everyone "
        "a red (6)_______ filled with money. The family eats a big dinner "
        "with (7)_______ and fish. At night, they light up the (8)_______ in "
        "front of the house. {name} wishes everyone good (9)_______.",
        [
            {"stem": "Grandmother gives everyone a red __________.",
             "opts": ["packet", "bucket", "towel"], "ans": 0},
            {"stem": "The family eats a big dinner with __________ and fish.",
             "opts": ["chicken", "stones", "books"], "ans": 0},
            {"stem": "They light up the __________ at night.",
             "opts": ["lanterns", "lampshades", "bicycles"], "ans": 0},
            {"stem": "{name} wishes everyone good __________.",
             "opts": ["luck", "fear", "noise"], "ans": 0},
        ],
        [{"name": G, "festival": F}
         for G, F in zip(GIRL, ["Chinese New Year", "Hari Raya", "Deepavali",
                                "Christmas", "Hari Gawai", "Chinese New Year"])]) +
    _mk(
        "The school canteen is open during recess. {name} buys (6)_______ "
        "with a cup of milk. His friend orders a bowl of (7)_______. The "
        "auntie puts the food on a (8)_______. The pupils queue up nicely and "
        "throw their rubbish into the (9)_______.",
        [
            {"stem": "{name} buys __________ with a cup of milk.",
             "opts": ["nasi lemak", "a crayon", "a ruler"], "ans": 0},
            {"stem": "His friend orders a bowl of __________.",
             "opts": ["noodles", "paint", "grass"], "ans": 0},
            {"stem": "The auntie puts the food on a __________.",
             "opts": ["plate", "pillow", "chair"], "ans": 0},
            {"stem": "They throw the rubbish into the __________.",
             "opts": ["bin", "pool", "sky"], "ans": 0},
        ],
        [{"name": B, "food": F} for B, F in zip(
            BOY, ["nasi lemak", "fried noodles", "mee goreng", "roti canai",
                  "fried rice", "curry mee"])])
)

# ---------------------------------------------------------------- Year 3 ---
CLOZE[3] = (
    _mk(
        "{name} and his family went to the beach on {day}. The sky was blue "
        "and the (6)_______ was warm. They swam in the sea and built a big "
        "(7)_______ on the sand. {name} found a beautiful (8)_______ near "
        "the water. His mother took many (9)_______ of the happy family.",
        [
            {"stem": "The __________ was warm at the beach.",
             "opts": ["sun", "fridge", "stove"], "ans": 0},
            {"stem": "They built a big __________ on the sand.",
             "opts": ["sandcastle", "house", "library"], "ans": 0},
            {"stem": "{name} found a beautiful __________ near the water.",
             "opts": ["shell", "ruler", "pillow"], "ans": 0},
            {"stem": "His mother took many __________ of the family.",
             "opts": ["photos", "books", "eggs"], "ans": 0},
        ],
        [{"name": B, "day": D} for B, D in zip(BOY, DAY)]) +
    _mk(
        "On a rainy {day}, {name} stayed at home. He read a storybook about "
        "a clever (6)_______ that saved the forest. He also drew a picture "
        "of a (7)_______ with a long tail. After that, he helped his mother "
        "bake a (8)_______. The house smelled of (9)_______ all evening.",
        [
            {"stem": "The story was about a clever __________.",
             "opts": ["fox", "table", "river"], "ans": 0},
            {"stem": "He drew a picture of a __________ with a long tail.",
             "opts": ["monkey", "fish", "turtle"], "ans": 0},
            {"stem": "He helped his mother bake a __________.",
             "opts": ["cake", "shoe", "kite"], "ans": 0},
            {"stem": "The house smelled of __________ all evening.",
             "opts": ["cake", "rain", "grass"], "ans": 0},
        ],
        [{"name": G, "day": D} for G, D in zip(GIRL, DAY)]) +
    _mk(
        "{name} visited a farm with his class. They saw cows eating "
        "(6)_______ in the field. The farmer showed them a barn full of "
        "(7)_______ and a pen of noisy (8)_______. The children fed the "
        "animals with fresh (9)_______. Everyone learned that farmers work "
        "very hard every day.",
        [
            {"stem": "The cows were eating __________ in the field.",
             "opts": ["grass", "soup", "chalk"], "ans": 0},
            {"stem": "The barn was full of __________.",
             "opts": ["hay", "sweets", "kites"], "ans": 0},
            {"stem": "There was a pen of noisy __________.",
             "opts": ["ducks", "lizards", "monkeys"], "ans": 0},
            {"stem": "The children fed the animals with fresh __________.",
             "opts": ["vegetables", "sand", "paper"], "ans": 0},
        ],
        [{"name": B} for B in BOY])
)

# ---------------------------------------------------------------- Year 5 ---
CLOZE[5] = (
    _mk(
        "Last month, {name} and his family travelled to Penang by (6)_______. "
        "They visited the famous street food stalls and ate (7)_______ for "
        "dinner. The next morning, they climbed the (8)_______ and saw the "
        "whole town below. On the way home, they bought (9)_______ as "
        "souvenirs for their friends.",
        [
            {"stem": "The family travelled to Penang by __________.",
             "opts": ["ferry", "bicycle", "tricycle"], "ans": 0},
            {"stem": "They ate __________ for dinner at the food stalls.",
             "opts": ["char koay teow", "ice cubes", "uncooked rice"], "ans": 0},
            {"stem": "They climbed the __________ and saw the town below.",
             "opts": ["hill", "flagpole", "escalator"], "ans": 0},
            {"stem": "They bought __________ as souvenirs.",
             "opts": ["keychains", "staples", "brooms"], "ans": 0},
        ],
        [{"name": B} for B in BOY]) +
    _mk(
        "Our school held a recycling competition on {day}. Each class had to "
        "collect (6)_______ and plastic bottles. The winning class recycled "
        "the most (7)_______ and won a trophy. Our teacher told us that "
        "recycling helps protect the (8)_______. We can also earn a little "
        "(9)_______ by selling old newspapers.",
        [
            {"stem": "Each class had to collect __________ and plastic bottles.",
             "opts": ["old newspapers", "fresh flowers", "breakfast food"], "ans": 0},
            {"stem": "The winning class recycled the most __________.",
             "opts": ["materials", "chairs", "photos"], "ans": 0},
            {"stem": "Recycling helps protect the __________.",
             "opts": ["environment", "pen", "furniture"], "ans": 0},
            {"stem": "We can earn a little __________ by selling old papers.",
             "opts": ["money", "wind", "noise"], "ans": 0},
        ],
        [{"name": B, "day": D} for B, D in zip(GIRL, DAY)]) +
    _mk(
        "{name} joined a school cookout to raise money for charity. The "
        "pupils sold homemade (6)_______ at the school gate. Parents came and "
        "bought the delicious food. All the (7)_______ collected was given to "
        "a local (8)_______. The pupils also made greeting (9)_______ to sell "
        "during the event.",
        [
            {"stem": "The pupils sold homemade __________ at the school gate.",
             "opts": ["cakes", "spanners", "drinks"], "ans": 0},
            {"stem": "All the __________ collected was given to charity.",
             "opts": ["money", "dust", "pebbles"], "ans": 0},
            {"stem": "The money was given to a local __________.",
             "opts": ["home", "cloud", "weekend"], "ans": 0},
            {"stem": "The pupils also sold greeting __________.",
             "opts": ["cards", "taps", "winds"], "ans": 0},
        ],
        [{"name": G} for G in GIRL[:6]])
)

# ---------------------------------------------------------------- Year 6 ---
CLOZE[6] = (
    _mk(
        "A fire broke out near the market on {day}. The firemen arrived "
        "quickly in their big (6)_______. They sprayed water at the burning "
        "(7)_______ until the fire went out. The people were told to stay "
        "(8)_______ and not go near the flames. The firemen rescued a small "
        "(9)_______ that was trapped inside a stall.",
        [
            {"stem": "The firemen arrived in their big __________.",
             "opts": ["engine", "banner", "tractor"], "ans": 0},
            {"stem": "They sprayed water at the burning __________.",
             "opts": ["stall", "building", "wood"], "ans": 0},
            {"stem": "The people were told to stay __________.",
             "opts": ["calm", "indoors", "outside"], "ans": 0},
            {"stem": "The firemen rescued a small __________.",
             "opts": ["kitten", "fire", "drumstick"], "ans": 0},
        ],
        [{"name": B, "day": D} for B, D in zip(GIRL, DAY)]) +
    _mk(
        "{name} visited a museum about life in the past on {day}. The guide "
        "showed them an old (6)_______ that people used to cook without "
        "electricity. The children tried writing with a (7)_______ and ink "
        "instead of a pencil. They learned that people once rode in "
        "(8)_______ pulled by horses. {name} was amazed that there were no "
        "(9)_______ long ago.",
        [
            {"stem": "The guide showed them an old __________.",
             "opts": ["stove", "machine", "tripod"], "ans": 0},
            {"stem": "They tried writing with a __________ and ink.",
             "opts": ["quill", "paintbrush", "torch"], "ans": 0},
            {"stem": "People once rode in __________ pulled by horses.",
             "opts": ["carts", "lifts", "boxes"], "ans": 0},
            {"stem": "{name} was amazed that there were no __________.",
             "opts": ["telephones", "books", "rivers"], "ans": 0},
        ],
        [{"name": G, "day": D} for G, D in zip(GIRL, DAY)]) +
    _mk(
        "Our class went to an adventure park on {day}. In the morning, we "
        "walked across a wobbly (6)_______ high above the ground. Then we "
        "learned to tie strong (7)_______ as the guides watched us. After "
        "lunch, everyone tried the flying (8)_______ that passed over the "
        "lake. The park staff reminded us to wear our (9)_______ at all "
        "times.",
        [
            {"stem": "We walked across a wobbly __________ high above the ground.",
             "opts": ["suspension bridge", "car seat", "picnic table"], "ans": 0},
            {"stem": "We learned to tie strong __________.",
             "opts": ["knots", "ribbons", "ladders"], "ans": 0},
            {"stem": "Everyone tried the flying __________ over the lake.",
             "opts": ["zip line", "rope", "leaf"], "ans": 0},
            {"stem": "The staff reminded us to wear our __________.",
             "opts": ["safety harness", "hats", "gloves"], "ans": 0},
        ],
        [{"name": B, "day": D} for B, D in zip(BOY, DAY)])
)