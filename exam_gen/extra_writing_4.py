# -*- coding: utf-8 -*-
"""Round 36: Year 4 Part 6/7 writing topics.

Years 1, 2, 3, 5 and 6 all had their own writing pools, so a Year 4 paper
either borrowed Year 5's prompts -- which the Year 4 JSU then flagged as
off-blue-print, because the ministry sheet wants Part 6 to be an offer, an
invitation, a prediction or advice -- or fell back to the built-in three
reference tasks and repeated them all term.

Every topic here is built from the official `Y4_RPT.docx` modules and from
what `JSU_Y4Y5Y6.xlsx` (Ref column O) allows Year 4 to assess:

============  ==========================================  =======  ==========
part          task                                        form     words
============  ==========================================  =======  ==========
Y4 Part 6     make/give predictions, offers, invitations,   email    30 - 50
              or advice
Y4 Part 7     narrate a factual event or experience,        email    60 - 80
              describe a person, place or object
============  ==========================================  =======  ==========

Every model answer is written to sit inside the band its own ``word_count``
prints, so the key never contradicts the question, and each prompt carries the
RPT module it belongs to so a themed paper can find it.
"""

_SHORT = {"lines": 6, "marks": 10, "word_count": "30 - 50 words"}
_LONG = {"lines": 12, "marks": 15, "word_count": "60 - 80 words"}


def _email(prompt, bullets, model, recipient, subject, theme, long=False):
    row = {"prompt": prompt, "bullets": list(bullets), "model": model,
           "recipient": recipient, "subject": subject, "theme": theme}
    row.update(_LONG if long else _SHORT)
    return row


# ---------------------------------------------------------------------------
# Year 4 Part 6 — short email, 30 - 50 words
# ---------------------------------------------------------------------------

SHORT = [
    _email("A food fair is coming to your school. Look at the poster and "
           "write an email to your friend. Accept the invitation and tell "
           "your friend why you want to go.",
           ["when the food fair is", "what food you will try",
            "why you want to go", "how you feel about it"],
           "Dear Farah, Our school is having a food fair on 12 March. I "
           "would love to go because I want to try the satay and the "
           "pandan cakes. It will be great fun with all my friends. Will "
           "you come with me? Yours, Farah",
           "Farah", "Food Fair", "Celebrations"),
    _email("Your cousin is visiting Malaysia next month. Write an email to "
           "him. Make an offer and tell him what he can do here.",
           ["when he is coming", "what you can show him",
            "an offer you make", "why he should come"],
           "Dear Danial, You are coming to Malaysia in April. I can take you "
           "to the park on Sunday and we can feed the ducks. You can also "
           "try nasi lemak for breakfast. Please come and stay at my house. "
           "See you soon, Farah",
           "Danial", "Your Visit", "Where Are You From?"),
    _email("It will rain this weekend. Write an email to your friend. Make "
           "a prediction about what your family will do and give a reason.",
           ["a prediction about the weather", "what your family will do",
            "a reason for your prediction"],
           "Dear Liyana, I think it will rain this weekend. My family will "
           "stay at home and we will play board games. We cannot go to the "
           "park because the ground will be wet. Have a nice weekend. "
           "Liyana",
           "Liyana", "This Weekend", "My Week"),
    _email("Your friend wants to learn about healthy food. Write an email to "
           "him. Give him some advice about what to eat every day.",
           ["food he should eat", "food he should avoid",
            "advice about drinks", "why healthy food is good"],
           "Dear Amir, You should eat fruit and vegetables every day. You "
           "should not eat too much sugar because it is bad for your teeth. "
           "Drink plenty of water, not soft drinks. Healthy food gives you "
           "energy to play. Yours, Farah",
           "Amir", "Healthy Food", "Eating Right"),
    _email("Your class is going to the zoo on Friday. Write an email to your "
           "friend. Ask for advice about the day and answer it too.",
           ["when you are going", "which animals you hope to see",
            "ask for advice", "the advice you give"],
           "Dear Siti, We are going to the zoo on Friday. I hope to see the "
           "monkeys and the elephants. Do you think we should bring water? "
           "Yes, we should, because it is very hot. See you then. Siti",
           "Siti", "School Zoo Trip", "Helping Out"),
    _email("A book sale is on at your school. Write an email to your friend "
           "and ask whether he or she will come with you.",
           ["when the book sale is", "where it is held",
            "invite your friend", "ask your friend to come"],
           "Dear Hakim, There is a book sale in our school hall on Friday. "
           "I want to buy a new story book. Would you like to come with me? "
           "It will start at ten o'clock. Please tell me. Your friend, Farah",
           "Hakim", "Book Sale", "Helping Out"),
    _email("Write an email to your friend about a new sport you want to try. "
           "Make an offer and ask your friend to try it with you.",
           ["the sport you want to try", "when you will play",
            "an offer you make", "ask your friend to join"],
           "Dear Nabil, I want to learn to swim this month. I will practise "
           "at the pool every Saturday morning. Would you like to come with "
           "me? I can teach you how to float. See you at the pool. Nabil",
           "Nabil", "Let's Swim", "Get Active!"),
    _email("Your friend is unhappy about a school test. Write an email to "
           "him. Ask for advice and give him some advice too.",
           ["how your friend feels", "advice you give",
            "what he should do next"],
           "Dear Hakim, You said you are unhappy about the test. I think you "
           "should not worry. You should read the paper again and count your "
           "mistakes. Then you can ask your teacher for help. Good luck. "
           "Farah",
           "Hakim", "About My Test", "What's the Matter?"),
]

# ---------------------------------------------------------------------------
# Year 4 Part 7 — longer email, 60 - 80 words
# ---------------------------------------------------------------------------

LONG = [
    _email("Last Sunday your family did something special together. Write "
           "an email to your friend and tell him or her about it.",
           ["when it was", "where you went", "who you were with",
            "what you did", "how you felt"],
           "Dear Farah, Last Sunday my family and I went to the market near "
           "the river. My father bought fresh fruit and my mother bought a "
           "new basket for vegetables. After that we stopped at a small "
           "cafe and I drank a glass of iced Milo. I felt tired but happy. "
           "It was a lovely day with my family. Yours, Liyana",
           "Farah", "Our Sunday", "In the Past", long=True),
    _email("You went to a new place last holiday. Write an email to your "
           "friend and tell him or her about the place and what you did "
           "there.",
           ["where you went", "how you got there", "what you did there",
            "who you went with", "how you felt"],
           "Dear Danial, Last holiday I went to a new park in our town with "
           "my cousins. We rode our bicycles there in the morning. At the "
           "park we played on the swing and fed the fish in the pond. In the "
           "afternoon we ate noodles at a small stall. I had a great day and "
           "I want to go again. Yours, Farah",
           "Danial", "My Holiday", "In the Past", long=True),
    _email("You met someone new at a party. Write an email to your friend "
           "and describe the person, and tell him or her what you did "
           "together.",
           ["who you met", "what the person is like", "where you met",
            "what you did together", "how you felt"],
           "Dear Siti, I met a new friend at my cousin's party last night. "
           "Her name is Nurul and she is eleven years old. She is tall and "
           "she has long black hair. She is very kind and funny. We played "
           "the board game and she won twice. I hope I can meet her again. "
           "Tell me more about your day. Yours, Farah",
           "Siti", "My New Friend", "Where Are You From?", long=True),
    _email("Your class did something to help the school garden. Write an "
           "email to your friend and tell him or her what happened.",
           ["what you did", "who you worked with", "what you planted",
            "how the garden looked at the end"],
           "Dear Liyana, Last Friday our class went to the school garden to "
           "help. We pulled out the old weeds and dug the soil. Then we "
           "planted some chilli and spinach. My friend Amir watered the "
           "plants after school. At the end the garden looked neat and "
           "green. I felt proud because we helped each other. We will look after it every week. Yours, Farah",
           "Liyana", "Our School Garden", "Helping Out", long=True),
    _email("Write an email to your friend about a day out at a zoo or a "
           "wildlife park. Tell him or her what you saw.",
           ["when you went", "which animals you saw",
            "what the animals were doing", "your favourite animal"],
           "Dear Nabil, I went to the wildlife park with my family last "
           "Saturday. We saw two elephants eating grass near the water. A "
           "monkey took my father's hat and ran away with it. The zebras "
           "were running together in the open field. My favourite animal was "
           "the parrot because it could talk. I took many photos. I saw many animals I had never seen before. Yours, "
           "Farah",
           "Nabil", "At the Wildlife Park", "Amazing Animals", long=True),
    _email("You played in a sports day at your school. Write an email to "
           "your friend and tell him or her about it.",
           ["which events you joined", "what happened in the race",
            "who won a prize", "how you felt"],
           "Dear Farah, Our school sports day was last Wednesday. I joined "
           "the hundred metres race and the throwing event. In the race I "
           "came second and my friend Amir came first. In the throwing "
           "event I threw six metres. Our class won the relay. I felt tired "
           "but very happy because we cheered together. Our teacher said we did a very good job. Yours, Siti",
           "Farah", "School Sports Day", "Get Active!", long=True),
    _email("Your friend is not feeling well. Write an email to ask how he or "
           "she is and to give some advice.",
           ["how your friend is", "what is wrong",
            "advice about resting", "advice about medicine"],
           "Dear Hakim, You said you are not feeling well. I am sorry to "
           "hear that. I think you should rest at home and drink plenty of "
           "warm water. You should also take your medicine after your meals. "
           "Please see the school nurse if you still have a fever. Get well "
           "soon. soon. Drink warm water and take good care of yourself. Yours, Farah",
           "Hakim", "Get Well Soon", "What's the Matter?", long=True),
    _email("Write an email to your friend about how your family celebrates "
           "a festival together.",
           ["which festival", "what you do before the festival",
            "what you do on the festival day", "who you celebrate with"],
           "Dear Siti, My family celebrates Hari Raya every year. On the day "
           "before, my mother makes ketupat and my father cleans the house. "
           "On the morning we wear new clothes and visit my grandparents. "
           "We eat together and my grandmother gives us ang pao. I enjoy "
           "this festival because the whole family is together. Tell me about yours. Yours, Farah",
           "Siti", "Our Family Festival", "Celebrations", long=True),
]

ESSAYS = {4: {"short": SHORT, "long": LONG}}
