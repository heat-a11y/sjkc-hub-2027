# -*- coding: utf-8 -*-
"""Round 26: ~50 curated writing topics for each Year 5 / Year 6 Part 6-7.

The pools that existed were too small to avoid repeats across a term, so this
module adds the missing topics:

===========================  ==========  ==========
part                        form         words
===========================  ==========  ==========
Y5 Part 6                   email         30 - 50
Y5 Part 7                   email         60 - 80
Y6 Part 6                   letter        30 - 50
Y6 Part 7                   email         60 - 80
===========================  ==========  ==========

Every model answer is written to sit inside the band its own ``word_count``
prints, so a teacher can hand the paper out without the key contradicting the
question.  ``tests.TestRound26WritingPools`` enforces both the sizes and the
word counts.
"""

#: Part 6/7 shared boilerplate, so each topic below only carries its content.
_SHORT = {"lines": 6, "marks": 10, "word_count": "30 - 50 words"}
_LONG = {"lines": 12, "marks": 15, "word_count": "60 - 80 words"}


def _email(prompt, bullets, model, recipient, subject, long=False):
    row = {"prompt": prompt, "bullets": list(bullets),
           "model": model, "recipient": recipient, "subject": subject}
    row.update(_LONG if long else _SHORT)
    return row


def _letter(prompt, bullets, model, salutation, closing):
    row = {"prompt": prompt, "bullets": list(bullets), "model": model,
           "salutation": salutation, "closing": closing}
    row.update(_SHORT)
    return row


# ---------------------------------------------------------------------------
# Year 5 Part 6 — short email, 30 - 50 words
# ---------------------------------------------------------------------------

Y5_SHORT = [
    _email("You are going to a sports day at your school next week. Write an "
           "email to your friend to tell him or her about it.",
           ["when the sports day is", "which events you will join",
            "what you must bring", "how you feel about it"],
           "Dear Aiman, Our sports day is on 18 July. I will join the hundred "
           "metres and the tug of war. Please bring a cap, water and your "
           "house colours. I feel excited but a little nervous. See you "
           "there! Your friend, Li",
           "aiman@email.com", "Our Sports Day"),
    _email("Your class is going to visit a nature park. Write an email to "
           "your cousin to tell him or her about the trip.",
           ["when you are going", "where the park is", "what you will do "
            "there", "what you must bring"],
           "Dear cousin, We are going to the nature park on 12 August. It is "
           "near the old rubber estate. We will look for birds and collect "
           "leaves. Bring a hat, insect repellent and a water bottle. Write "
           "back soon. Your cousin, Farah",
           "cousin@email.com", "Our Nature Park Trip"),
    _email("Your neighbour has a new puppy. Write an email to your friend to "
           "tell him or her about the puppy.",
           ["what the puppy looks like", "what it likes to eat",
            "when you can play with it", "how you feel"],
           "Dear Wei Ling, My neighbour has a new puppy. It is brown with "
           "white paws and a very long tail. It likes milk and biscuits. I can "
           "play with it every Saturday. I think it is lovely. Your "
           "friend, Siti",
           "weiling@email.com", "My Neighbour's New Puppy"),
    _email("You watched a match at your school last weekend. Write an email "
           "to your friend about it.",
           ["which match you watched", "who played", "the final score",
            "which moment you liked best"],
           "Dear Danial, Our school football match was last Saturday. The Blue "
           "Team played the Red Team. The final score was three to one. I "
           "liked the last goal best because it was so exciting. Your "
           "friend, Hakim",
           "danial@email.com", "Our School Football Match"),
    _email("The school canteen has changed its menu. Write an email to your "
           "friend to tell him or her about the new food.",
           ["what is sold now", "what the prices are", "what you tried",
            "what you think of the change"],
           "Dear Farah, The school canteen has a new menu. It sells nasi lemak "
           "for three ringgit and a fruit salad for two ringgit. I tried the "
           "chicken noodles. They are tasty and not expensive. Your "
           "friend, Mei",
           "farah@email.com", "The New Canteen Menu"),
    _email("Your family is moving to a new house next month. Write an email "
           "to your friend to tell him or her about it.",
           ["where you are moving", "what your new school is like",
            "what you will miss", "how you feel"],
           "Dear Aina, We are moving to a new house in September. My new "
           "school is bigger and has a science lab. I will miss my old friends "
           "and our garden. I am excited and a little sad. Your "
           "friend, Sofia",
           "aina@email.com", "We Are Moving"),
    _email("You joined a new club at school. Write an email to your friend to "
           "tell him or her about it.",
           ["which club you joined", "when it meets", "what you do there",
            "why you joined"],
           "Dear Jun, I joined the chess club. It meets every Wednesday at two "
           "o'clock in the library. We play practice games and learn new "
           "openings. I joined because my brother plays chess. Do you want "
           "to join too? Your friend, Ali",
           "jun@email.com", "My New Chess Club"),
    _email("Your school held a gotong-royah last week. Write an email to "
           "your friend about the evening.",
           ["what was cooked", "who came", "what games you played",
            "when you went home"],
           "Dear Kumar, Our school had a gotong-royah on Friday evening. My "
           "mother cooked curry chicken and ketupat. Many parents came. We "
           "played the coconut game and won prizes. I went home at nine. "
           "Your friend, Rina",
           "kumar@email.com", "Our Gotong-Royah Evening"),
    _email("You bought a book from a book sale. Write an email to your friend "
           "to tell him or her about the book.",
           ["what the book is about", "who wrote it", "how much you paid",
            "why you chose it"],
           "Dear Sofia, I bought a book at the school book sale. It is about a "
           "boy who lives on a fishing boat. The author is a Malaysian writer. "
           "I paid four ringgit for it. I chose it because the cover "
           "looks exciting. Your friend, Daniel",
           "sofia@email.com", "A Book From the Sale"),
    _email("Your town cleaned up a rubbish dump. Write an email to your "
           "friend to tell him or her about it.",
           ["where the dump was", "who cleaned it", "what was collected",
            "what the place looks like now"],
           "Dear Li Hong, The rubbish dump behind our flats was cleaned on "
           "Sunday. Forty volunteers came, including my father. We collected "
           "twenty big bags. Now there is a small garden there. Your friend, "
           "Mei",
           "lihong@email.com", "Our Cleaned-Up Dump"),
    _email("You are learning to ride a bicycle. Write an email to your friend "
           "to tell him or her about it.",
           ["when you started", "who is teaching you", "how often you "
            "practise", "how well you can do now"],
           "Dear Farah, I am learning to ride a bicycle. My uncle started "
           "teaching me last month. We practise every Sunday at the field. I "
           "can go straight now, but I still cannot turn quickly. Your "
           "friend, Amir",
           "farah@email.com", "Learning to Ride a Bike"),
    _email("A drama show is coming to your town. Write an email to your "
           "friend to invite him or her.",
           ["what the show is", "when and where it is", "how much a ticket "
            "is", "who you are going with"],
           "Dear Nadia, A drama show is coming to the town hall on 25 May. It "
           "is about a village boy. A ticket costs ten ringgit for students. I "
           "am going with my cousins. Please come with us. Your friend, "
           "Hafiz",
           "nadia@email.com", "A Drama Show in Town"),
    _email("Your school collected used books for a village school. Write an "
           "email to your friend to tell him or her what you did.",
           ["what you collected", "how many books", "who you worked with",
            "where the books went"],
           "Dear Ravi, Our school collected used books for the village school. "
           "I brought four books from home. My class packed one hundred and "
           "twenty books in blue boxes. A van took them away on "
           "Friday. Your friend, Nabila",
           "ravi@email.com", "Books for the Village School"),
    _email("Your brother is learning to drive. Write an email to your cousin "
           "to tell him or her how he is doing.",
           ["when he started", "who is teaching him", "what he can do now",
            "when he may drive alone"],
           "Dear Jasmine, My brother started driving lessons last month. His "
           "teacher is Mr Lim. He can reverse and park now, but he still "
           "nerves at junctions. He may drive alone next year. Your cousin, "
           "Ismail",
           "jasmine@email.com", "My Brother's Driving Lessons"),
    _email("You helped in your school's garden. Write an email to your "
           "friend to tell him or her about it.",
           ["what you planted", "who worked with you", "how often you water "
            "it", "what you hope to grow"],
           "Dear Wei Jian, Our class garden is doing well. We planted chilli "
           "and spinach in March. Mr Rajoo taught us. We water it every "
           "morning. I hope we can sell the vegetables in June. Your friend, "
           "Liyana",
           "weijian@email.com", "Our School Garden"),
    _email("Your school had a water-saving week. Write an email to your "
           "friend to tell him or her what was done.",
           ["why the week was held", "what pupils had to do",
            "how much water was saved", "what you think"],
           "Dear Hani, Our school had a water-saving week because the taps "
           "were dry. We used a metal mug and closed the tap while brushing. "
           "We saved enough for one day's use. I think every school should "
           "do this. Your friend, Zul",
           "hani@email.com", "Our Water-Saving Week"),
    _email("You watched a puppet show at a school hall. Write an email to "
           "your friend about it.",
           ["what kind of show it was", "what the story was about",
            "what the music was like", "whether you enjoyed it"],
           "Dear Farah, There was a puppet show at our school hall. It used "
           "shadow puppets. The story was about a clever monkey and a greedy "
           "crocodile. The music was funny and fast. I enjoyed it very much. "
           "Your friend, Bella",
           "farah@email.com", "A Puppet Show"),
    _email("Your class visited a farm. Write an email to your friend to tell "
           "him or her about the visit.",
           ["where the farm is", "what animals you saw", "what you learnt",
            "what you did there"],
           "Dear Hakim, Our class visited a fruit farm near the town. We saw "
           "goats, ducks and rows of papaya trees. The farmer showed us how to "
           "pick fruit. I picked two baskets of mangoes. Your friend, "
           "Nurul",
           "hakim@email.com", "Our Visit to a Farm"),
    _email("Your friend lost a pencil case. Write an email to tell him or her "
           "what you found.",
           ["what it looks like", "where you found it", "what is inside it",
            "when you will return it"],
           "Dear Sofia, I found your pencil case under the back staircase. It "
           "is blue with a rabbit on the front. Inside there are two pencils, "
           "a ruler and an eraser. I will keep it in my bag. See you "
           "tomorrow. Your friend, Daniel",
           "sofia@email.com", "I Found Your Pencil Case"),
    _email("Your school library started a reading challenge. Write an email "
           "to your friend to tell him or her about it.",
           ["what the challenge is", "how many books you must read",
            "what you have read", "what you get at the end"],
           "Dear Jun Hao, Our library started a reading challenge. We must "
           "read six books this term. I have finished two adventure stories. "
           "At the end we get a certificate and a bookmark. Your friend, "
           "Siti",
           "junhao@email.com", "Our Reading Challenge"),
    _email("You tried cooking a new dish. Write an email to your friend to "
           "tell him or her about it.",
           ["what dish you cooked", "who taught you", "what went wrong",
            "how it turned out"],
           "Dear Nadia, I tried cooking curry noodles with my aunt. She showed "
           "me how to fry the spices. I burnt the onions the first "
           "time. The second try was very tasty. Your friend, Aiman",
           "nadia@email.com", "I Tried a New Dish"),
    _email("Your class did a survey about what pupils eat for breakfast. "
           "Write an email to your friend to report the results.",
           ["how many pupils you asked", "what was the most popular food",
            "what the least popular food was", "what surprised you"],
           "Dear Kumar, My class asked sixty pupils about breakfast. Nasi "
           "lemak was the most popular. Bread and eggs came last. I was "
           "surprised that few pupils eat cereal. Your friend, Amira",
           "kumar@email.com", "Our Breakfast Survey"),
    _email("You went to a night market with your family. Write an email to "
           "your friend about the evening.",
           ["when you went", "what you ate", "what you bought",
            "what you liked most"],
           "Dear Farah, We went to the night market on Saturday evening. I ate "
           "satay and drank sugarcane juice. Mother bought a blue "
           "sarong for me. I liked the food stall best. Your friend, Wei",
           "farah@email.com", "Our Night Market Evening"),
    _email("Your school built a small garden for butterflies. Write an "
           "email to your friend to tell him or her about it.",
           ["where the garden is", "what flowers were planted",
            "how the class made it", "what insects you may see"],
           "Dear Li Hong, Our school made a butterfly garden behind the "
           "science block. We planted lantana and ixora flowers. Pupils in my "
           "group made the signboards. Butterflies and bees may come soon. "
           "Your friend, Mei",
           "lihong@email.com", "Our Butterfly Garden"),
    _email("You are learning to use a sewing machine. Write an email to your "
           "friend to tell him or her about it.",
           ["who is teaching you", "what you have made", "what was hard",
            "what you will make next"],
           "Dear Sofia, I am learning to use a sewing machine at home. My "
           "grandmother is teaching me. I have made a cushion cover. Turning "
           "the corner is still hard. Next I want to make a small bag. Your "
           "friend, Daniel",
           "sofia@email.com", "Learning to Sew"),
    _email("Your class cleaned a beach near your village. Write an email to "
           "your friend to tell him or her about it.",
           ["where the beach is", "how many people came",
            "what rubbish you collected", "what you found"],
           "Dear Amir, Our class cleaned the beach near my village on "
           "Saturday. Forty people came, including some fishermen. We filled "
           "fifteen bags with plastic and glass. I found a blue shoe. Your "
           "friend, Nadhirah",
           "amir@email.com", "Cleaning the Beach"),
    _email("Your school showed a science experiment to young pupils. Write "
           "an email to your friend about the show.",
           ["which experiment was shown", "what it showed",
            "which pupils watched", "what you enjoyed"],
           "Dear Hani, My team showed a science experiment to pupils from the "
           "nearest kindergarten. We made a small volcano. The pupils were "
           "quiet at first, then very excited. I enjoyed answering their "
           "questions. Your friend, Zul",
           "hani@email.com", "A Science Show for Young Pupils"),
    _email("You planted a mango tree in your yard. Write an email to your "
           "friend to tell him or her about it.",
           ["when you planted it", "how you planted it", "how you water it",
            "when you hope to eat the fruit"],
           "Dear Ravi, My father and I planted a mango tree in our yard last "
           "Sunday. We dug a deep hole and put in compost. We water it every "
           "evening. I hope to eat the fruit in four years. Your friend, "
           "Nabila",
           "ravi@email.com", "My Mango Tree"),
    _email("Your school exchange programme sent pupils to another town. "
           "Write an email to your friend to tell him or her about the trip.",
           ["where the pupils went", "how long they stayed",
            "what they saw", "what they learned"],
           "Dear Jasmine, Pupils from my school went to Kuala Selangor last "
           "week. They stayed two nights with families there. They visited a "
           "bird park and a museum. They learned that small towns have rich "
           "history. Your cousin, Ismail",
           "jasmine@email.com", "Our Exchange Trip"),
    _email("You helped your mother at a cake sale. Write an email to your "
           "friend to tell him or her about it.",
           ["where the sale was", "what you sold",
            "how much money you collected", "the best thing that happened"],
           "Dear Jun, we helped at the cake sale outside the market on "
           "Saturday. I sold cupcakes and my mother sold cookies. We collected "
           "ninety ringgit for the school fund. A small boy bought "
           "six cupcakes with his pocket money. Your friend, Ali",
           "jun@email.com", "Our Cake Sale"),
    _email("Your class visited a bakery. Write an email to your friend to "
           "tell him or her what you learned.",
           ["where the bakery is", "what you saw being made",
            "how the baker started", "what you bought"],
           "Dear Farah, our class visited a bakery in town on Tuesday. We "
           "watched the baker shape the dough and put it in the hot oven. He "
           "said he started with one small oven in his kitchen. I bought a "
           "bread roll and it was still warm. Your friend, Mei",
           "farah@email.com", "Our Visit to a Bakery"),
]

# ---------------------------------------------------------------------------
# Year 5 Part 7 — longer email, 60 - 80 words
# ---------------------------------------------------------------------------

Y5_LONG = [
    _email("You stayed with a family in a small village for three days. Write "
           "an email to your friend to tell him or her about the visit.",
           ["where the village is", "who you stayed with",
            "what you did each day", "what you ate",
            "how the village was different from town", "how you felt"],
                      "Dear Wei Lin, Last weekend my class stayed in a village near Kuala "
           "Selangor. I stayed with a family of six. On the first day we fed "
           "their chickens and picked mangoes. The next day we helped in the "
           "rice field. On the last morning we ate coconut rice for breakfast. "
           "There were no shops and the roads were quiet. I miss the fresh air "
           "already. Write and tell me what you are doing this weekend. Your "
           "friend, Mei",
           "weilin@email.com", "My Visit to a Village", long=True),
    _email("Your school held a science fair. Write an email to your friend to "
           "tell him or her about it.",
           ["when the fair was", "what projects were shown",
            "which project you liked best", "what prize you or your team won",
            "what you learned"],
                      "Dear Aiman, Our school held a science fair last Thursday. There "
           "were eighteen projects in the hall. My group showed a model of a "
           "rainwater collector. I liked a volcano model best because the "
           "smoke really came out. We won second prize for our design. I "
           "learned that old ideas can be very clever. It was a busy, happy "
           "day. Your friend, Li",
           "aiman@email.com", "Our School Science Fair", long=True),
    _email("You joined a debate about phones in school. Write an email to your "
           "friend to tell him or her your opinion.",
           ["what the topic was", "the two sides", "which side you chose",
            "two reasons for your side", "how the debate went"],
           "Dear Kumar, Our class had a debate about phones in school. One "
           "team said phones help us study and the other said they distract "
           "us. I was on the side that says phones should be banned in class "
           "but kept outside. First, we cannot focus when a phone buzzes. "
           "Second, games are hard to stop. Our team won by one vote. Your "
           "friend, Siti",
           "kumar@email.com", "My Thoughts on Phones in School", long=True),
    _email("Your class raised money for a charity walk. Write an email to your "
           "friend to tell him or her how it went.",
           ["what the walk was for", "how far you walked",
            "how much money you collected", "who helped you",
            "how you felt"],
           "Dear Farah, Our class held a charity walk on Sunday morning. We "
           "walked five kilometres to the town park for a children's home. My "
           "group collected one hundred and eighty ringgit. My aunt gave us a "
           "big box of buns to sell. It was tiring but our legs did not hurt "
           "at all. I am proud that we helped. Your friend, Mei",
           "farah@email.com", "Our Charity Walk", long=True),
    _email("You spent a week at a farm during the school holiday. Write an "
           "email to your friend to tell him or her about it.",
           ["where the farm is", "what work you did",
            "what animals you looked after", "what you ate",
            "the best and worst part", "how you felt at the end"],
                      "Dear Sofia, I spent five days on a fruit farm in Perak. I fed "
           "hens, picked oranges and repaired a fence. The best part was "
           "riding the tractor. The worst part was waking at five. I ate "
           "simple food but it tasted good. I now understand where fruit comes "
           "from. Next time I want to help with the mangoes as well. Your "
           "friend, Daniel",
           "sofia@email.com", "My Week on a Farm", long=True),
    _email("Your class planted a mini forest along the road. Write an email to "
           "your friend to tell him or her about the project.",
           ["where the trees were planted", "how many were planted",
            "what kind of trees", "how the class worked together",
            "what the plan is for the future"],
                      "Dear Daniel, Our class started a mini forest beside the road to "
           "our school. We planted sixty saplings of mahogany and bamboo. We "
           "dug holes in pairs, so the work went fast. Our teacher says the "
           "trees will give shade in ten years. We will water them every "
           "Monday. Some parents have promised us fruit trees too, and we have "
           "made a small signboard with the year we planted them. Your friend, "
           "Sofia",
           "daniel@email.com", "Our Mini Forest Project", long=True),
    _email("You attended a traditional wedding. Write an email to your friend "
           "to tell him or her about it.",
           ["whose wedding it was", "where it was held", "what you wore",
            "what food was served", "what games were played",
            "how you felt"],
                      "Dear Nadia, I went to my cousin's wedding last Sunday. It was held "
           "in a hall near the town. I wore a pink baju kurung my mother "
           "sewed. We ate nasi kerabu and grilled fish. There was a silat "
           "performance and a money-giving ceremony. I felt proud to be part "
           "of the family day. We left late, after the moon rose. Your friend, "
           "Hafiz",
           "nadia@email.com", "A Traditional Wedding", long=True),
    _email("You read a book for school and want to share it. Write an email to "
           "your friend to recommend the book.",
           ["the title and author", "what the story is about",
            "which part you liked most", "who would like it",
            "why you want your friend to read it"],
           "Dear Wei Jian, I want to tell you about a book I read for school. "
           "It is Journey to the River by SITI NURHASNAH. The story follows a "
           "girl who rows a boat with her grandfather. My favourite part is "
           "when they meet the deer. I think you would like it because it is "
           "quiet and kind. Please borrow it after me. Your friend, Liyana",
           "weijian@email.com", "A Book I Recommend", long=True),
    _email("Your town's river was cleaned by volunteers. Write an email to "
           "your friend to tell him or her what happened.",
           ["why the river was dirty", "how many volunteers came",
            "what was removed from the water", "what the plan is now",
            "how the river looks today"],
                      "Dear Hani, The river behind our town was full of plastic bottles "
           "and tin cans. Last Sunday two hundred volunteers came to clean it. "
           "We pulled out thirty big bags of rubbish in three hours. Fish "
           "mongers said they saw small fish again last week. The town council "
           "will put a bin near the bridge now. Everyone is watching to see if "
           "the water clears. Your friend, Zul",
           "hani@email.com", "Cleaning Our Town River", long=True),
    _email("You took part in a school heritage walk. Write an email to your "
           "friend to tell him or her what you saw.",
           ["where the walk was", "which old buildings you saw",
            "who told you the history", "what you learned about the town",
            "what you would show a visitor"],
                      "Dear Rafi, Our class joined a heritage walk in the old town on "
           "Saturday. We saw a Chinese temple from 1890, a baker's shop and a "
           "station that still uses wooden doors. An old uncle told us how the "
           "market was in his father's time. I would show a visitor the temple "
           "and the wet market. The whole walk took two hours. Your friend, "
           "Hakim",
           "rafi@email.com", "Our Heritage Walk", long=True),
    _email("You learned to cook a family recipe for the first time. Write an "
           "email to your friend to tell him or her about it.",
           ["whose recipe it is", "what the dish is", "what is in it",
            "which step was hardest", "how the dish turned out"],
           "Dear Siti, Last Sunday I cooked my grandmother's ayam berkuah pot "
           "chicken. The recipe needs coconut milk, lemongrass and forty "
           "minutes of slow stirring. The hardest part was keeping the fire "
           "small so the milk did not split. My family finished the whole pot. "
           "I will cook it again next month. I wrote every step in a notebook "
           "so I can do it alone. Your friend, Adib",
           "siti@email.com", "My First Real Recipe", long=True),
    _email("Your class made a short film about pollution. Write an email to "
           "your friend to tell him or her about the project.",
           ["what your group decided to make", "how you wrote the story",
            "who acted in the film", "how you filmed it",
            "where the film was shown"],
                      "Dear Daniel, My group made a three-minute film about pollution for "
           "the school showcase. We wrote the story about a boy who finds a "
           "river full of rubbish. My cousin acted as the boy. We filmed on "
           "phones by the canteen and edited the video at night. It was shown "
           "in the hall on Friday. Thirty people came to watch it. Your "
           "friend, Sofia",
           "daniel@email.com", "Our Short Film About Pollution", long=True),
    _email("You went on a school trip to a wetland. Write an email to your "
           "friend to tell him or her about the trip.",
           ["where the wetland is", "what birds you saw",
            "what the guide told you", "what you did there",
            "why the wetland matters"],
                      "Dear Nadia, Our school trip went to a wetland near the coast. We "
           "saw herons, kingfishers and a lot of mudskippers. The guide said "
           "the wetland is a stopover for birds travelling north. We walked on "
           "a board walk and kept quiet. It filters dirty water, so we must "
           "keep it clean. We took our rubbish home in three bags and our "
           "teacher praised us for it. Your friend, Hafiz",
           "nadia@email.com", "Our Wetland Trip", long=True),
    _email("You are leaving your old school. Write an email to your teacher to "
           "thank her or him.",
           ["how long you were at the school", "what you learned",
            "a memory you will keep", "what you will miss",
            "what you will do next"],
           "Dear Miss Tan, I am writing to thank you for four good years at SK "
           "Taman Melati. You always answered my questions after class, and "
           "you showed me how to revise for tests. I will keep the memory of "
           "the class reading hour, when everyone read aloud together. I will "
           "miss our morning assembly and your jokes. I hope to study hard at "
           "my new school. Thank you for everything. Your pupil, Farah",
           "farah@email.com", "Thank You, Miss Tan", long=True),
    _email("Your school started a breakfast club for pupils who come without "
           "food. Write an email to your friend to tell him or her about it.",
           ["why the club started", "what the club gives out",
            "how many pupils come", "how you helped",
            "what you think will happen"],
           "Dear Jun, Our school started a breakfast club because some pupils "
           "arrive with nothing to eat. Every morning we give out bread, milk "
           "and fruit. About thirty pupils come. I help for one period before "
           "class. I think it will help them study better. A teacher keeps a "
           "list so nobody is left out, and parents send extra on Fridays. "
           "Last term we needed new bowls and they came in one day. Your "
           "friend, Ali",
           "jun@email.com", "Our School Breakfast Club", long=True),
    _email("You watched a play about a folk tale. Write an email to your "
           "friend to tell him or her about it.",
           ["which folk tale it was", "who acted and sang",
            "what the costumes were like", "what you liked about the music",
            "whether you would see it again"],
           "Dear Kumar, Our drama club performed the folk tale Badang Paloh at "
           "the community hall. Nine students acted, and four sang with a "
           "drum. The costumes were bright cotton and papier-mache masks. I "
           "liked the drum song best because the whole hall clapped "
           "along. I would go again next year. We practised every evening for "
           "two months and painted the masks ourselves in art class. Your "
           "friend, Rina",
           "kumar@email.com", "A Play About a Folk Tale", long=True),
    _email("Your class surveyed the neighbourhood about stray dogs. Write an "
           "email to your friend to report the findings and your opinion.",
           ["how many people you asked", "what most people said",
            "what problem they face", "what you think should be done",
            "what your class did next"],
                      "Dear Hafiz, My group asked seventy people about stray dogs. Most "
           "of them said the dogs are too many near the food court. Fifty "
           "people wanted the council to catch them, and twenty wanted a "
           "shelter instead. We think a shelter with a vet is fairer. Now we "
           "are collecting signatures for the council. We have already got one "
           "hundred and twenty names. Your friend, Li Hong",
           "hafiz@email.com", "Our Survey on Stray Dogs", long=True),
    _email("You spent a day helping at a community library. Write an email to "
           "your friend to tell him or her about the day.",
           ["where the library is", "what your job was",
            "how many people came", "what you learned about books",
            "how you felt at the end of the day"],
           "Dear Amira, I volunteered at the community library in my village "
           "on Sunday. My job was to sort donated books and write the code on "
           "each spine. Forty people came, and most were children. I learned "
           "that a good cover is not always a good story. My hands smelled of "
           "dust and paper all evening. I want to go back next month. Your "
           "friend, Farah",
           "amira@email.com", "A Day at the Community Library", long=True),
    _email("You had to give a talk about your hobby. Write an email to your "
           "friend to tell him or her how it went.",
           ["what your hobby is", "how long you have done it",
            "what you showed the class", "what questions you were asked",
            "how you felt afterwards"],
                      "Dear Rafi, Last week I gave a talk about my hobby, collecting "
           "stamps. I have collected them for four years. I showed my album "
           "and explained how I started. The class asked about rare stamps and "
           "how much my oldest one costs. I answered as best I could. I was "
           "nervous but glad I finished. My mother said she was proud of me. "
           "Your friend, Hakim",
           "rafi@email.com", "My Talk About Collecting Stamps", long=True),
    _email("Your class built a small pond to study water life. Write an email "
           "to your friend to tell him or her about it.",
           ["why the class built it", "how you dug the pond",
            "what lives in it now", "what you observed",
            "how you look after it"],
                      "Dear Siti, Our class dug a small pond behind the science lab to "
           "study water life. It took three afternoons. Now there are water "
           "lice and tiny plants. We can see frog eggs in March. We test the "
           "water every Friday and keep it clean. We also made a chart on the "
           "wall and marked the pH every week. The frogs came back in April "
           "and put eggs on the weeds. Your friend, Adib",
           "siti@email.com", "Our Class Pond", long=True),
    _email("You went to a market with your grandmother. Write an email to "
           "your friend to tell him or her about it.",
           ["where you went", "what your grandmother bought",
            "what she taught you", "what food you ate",
            "what you enjoyed most"],
                      "Dear Nadia, I went to the morning market with my grandmother on "
           "Sunday. She bought fish, chillies and two baskets of fruit. She "
           "taught me to choose the freshest vegetables and to count the "
           "change twice. We ate nasi lemak wrapped in paper at the stall. I "
           "liked listening to the sellers shout best. We came home with two "
           "big bags. Your friend, Hafiz",
           "nadia@email.com", "A Morning with My Grandmother", long=True),
    _email("Your school exchanged pen pals with a school overseas. Write an "
           "email to your pen pal to introduce yourself.",
           ["your name and age", "where you live and study",
            "what your school is like", "what you like to do",
            "two questions you want to ask them"],
           "Dear Pen Pal, My name is Farah and I am eleven years old. I live "
           "in a small town in Malaysia. My school has a big field and a new "
           "library. I like drawing animals and I play badminton on Saturdays. "
           "What is your school like? Do you play any sport? I "
           "cannot wait to read your letter. Your pen pal, Farah",
           "penpal@email.com", "Hello from Malaysia", long=True),
    _email("You helped your family after a storm. Write an email to your "
           "friend to tell him or her what happened.",
           ["what the storm did", "what your family had to do",
            "who helped you", "what was damaged",
            "how your family is doing now"],
                      "Dear Jun, A storm with strong wind hit our village on Sunday "
           "night. Six trees fell and the metal roof of our shed flew off. My "
           "family and two neighbours worked until dawn to lift the branches. "
           "Nobody was hurt. Now we have a tarpaulin over the shed and the "
           "trees are being cut. The council will send help on Friday. Your "
           "friend, Ali",
           "jun@email.com", "After the Storm", long=True),
    _email("You are planning a farewell party for a friend who is moving "
           "away. Write an email to your friend to tell him or her what is "
           "planned.",
           ["when the party is", "where it will be held",
            "what the class will do", "what you will give",
            "how you feel about the move"],
           "Dear Wei Lin, We are planning a farewell party for you on 28 July. "
           "It will be in the school hall after class. Our class will sing and "
           "show a video of our trips. I will give you a photo album that we "
           "made. I am happy for you, but I will miss you very much. Please "
           "bring your swimming things too, because we will play after lunch. "
           "Your friend, Li",
           "weilin@email.com", "A Party for You", long=True),
    _email("Your class tested the water quality of a pond. Write an email to "
           "your friend to explain the results.",
           ["what you tested", "what the results were",
            "what the numbers mean", "what the class will do next",
            "what you learned"],
                      "Dear Sofia, Our science group tested the water of the pond behind "
           "school. We checked pH, smell and clarity. The pH was 7, which is "
           "good, but the water was cloudy and smelly. The test sheet says "
           "cloudy water cannot hold much oxygen. We will put plants in the "
           "pond and test again in a month. My teacher says the chart will go "
           "up on the wall. Your friend, Daniel",
           "sofia@email.com", "Our Pond Water Test", long=True),
    _email("Your class visited a market to learn about prices. Write an email "
           "to your friend to tell him or her what you learnt.",
           ["where the market is", "which stall you visited",
            "how prices are different", "how you worked out the change",
            "what surprised you"],
                      "Dear Kumar, Our maths class went to the wet market on Tuesday. We "
           "visited the vegetable stall and the fish stall. Vegetables cost "
           "less at the market than in the supermarket. We had to work out the "
           "change for three buyers. I was surprised how quickly the price "
           "changes. We also asked the fishmonger how he decides his price, "
           "and he told us about the early market. Your friend, Siti",
           "kumar@email.com", "Learning Prices at the Market", long=True),
    _email("You joined a chess club match against another school. Write an "
           "email to your friend to tell him or her how it went.",
           ["where the match was played", "how long it lasted",
            "which moves you used", "how the result went",
            "what you will practise next"],
                      "Dear Wei Jian, our chess club played the Ampang school team on "
           "Saturday. The match lasted ninety minutes. I used the Sicilian "
           "defence and won my second game in the last ten minutes. We lost "
           "the match two boards to one. Next week I will study the endgame "
           "with my coach. I lost my first game to a pupil in Standard One, "
           "which was embarrassing but good for me. Your friend, Liyana",
           "weijian@email.com", "Our Chess Match", long=True),
    _email("Your class collected old newspapers to sell. Write an email to "
           "your friend to report what happened.",
           ["why you collected them", "how much you collected",
            "who bought the paper", "how much money you made",
            "what you will do with the money"],
                      "Dear Hani, our class collected old newspapers for a week because "
           "recycling pays a small amount. We tied nine big bundles. A man "
           "from a recycling shop came with a lorry and paid us forty-five "
           "ringgit. We decided to buy new books for the reading corner. It "
           "was heavy work but it was worth it. We will do it again before the "
           "exams. Your friend, Zul",
           "hani@email.com", "Selling Old Newspapers", long=True),
    _email("You are learning to swim. Write an email to your friend to tell "
           "him or her how you are getting on.",
           ["when you started", "who teaches you", "what you can do now",
            "what still frightens you", "when you will have a lesson"],
           "Dear Rafi, I started swimming lessons in January at the community "
           "pool. My teacher is Uncle Din. I can float with my eyes open and "
           "swim twenty metres now. Putting my face in the water still makes "
           "me panic. I have a lesson every Saturday at eight. My father comes "
           "to watch, and last week I swam the length of the pool twice "
           "without stopping. Your friend, "
           "Hakim",
           "rafi@email.com", "My Swimming Lessons", long=True),
    _email("Your school showed a heritage exhibition. Write an email to your "
           "friend to describe what was in it.",
           ["where the exhibition was", "what was on display",
            "which object interested you most", "what the guide explained",
            "whether the class made anything"],
           "Dear Siti, our school held a heritage exhibition in the hall last "
           "week. There were old photographs, a grandmother's cooking pot and "
           "a wooden school desk from 1950. I was most interested in the desk "
           "because my grandfather had the same one. The guide explained that "
           "pupils once wrote with ink and one slate each. Our class made "
           "clay tiles. Your friend, Adib",
           "siti@email.com", "Our Heritage Exhibition", long=True),
    _email("You looked after your neighbour's dog for a week. Write an email "
           "to your friend to tell him or her about it.",
           ["why you looked after it", "what the dog is like",
            "what you did every day", "the funniest thing it did",
            "how you felt when the owner came back"],
           "Dear Nadia, my neighbour asked me to feed her dog for a week while "
           "she went to Singapore. The dog is called Bim, and he is a brown "
           "labrador. He needs two walks a day and he sleeps under my table "
           "while I do homework. The funniest thing was that he ate my "
            "sock. I was sad when the owner came back. Your friend, Hafiz",
           "nadia@email.com", "Looking After Bim", long=True),
]

# ---------------------------------------------------------------------------
# Year 6 Part 6 — short letter, 30 - 50 words
# ---------------------------------------------------------------------------

Y6_LETTERS = [
    _letter("You won a prize in a school competition. Write a letter to your "
            "friend to tell him or her about it.",
            ["what competition it was", "what you did",
             "what prize you won", "how you felt"],
            "Dear Wei Lin, I won second prize in our school's storytelling "
            "contest. I told the story of a farmer and his buffalo. The judge "
            "said my voice was clear. I felt proud and my mother cried. Your "
            "friend, Mei",
            "Dear Wei Lin,", "Your friend,"),
    _letter("You are moving to a new school next term. Write a letter to your "
            "current teacher to say goodbye.",
            ["how long she or he has taught you", "what you learnt",
             "a memory you will keep", "what you wish for her or him"],
                        "Dear Miss Tan, I am writing to say goodbye before I move to a new "
            "school. You have taught me for three years. I learnt to read "
            "faster and to speak up in class. I will keep the memory of story "
            "hour. Thank you for everything. Your pupil, Farah",
            "Dear Miss Tan,", "Your pupil,"),
    _letter("You bought a bicycle with your own pocket money. Write a letter "
            "to your cousin to tell him or her about it.",
            ["how you saved for it", "what colour it is",
             "where you ride it", "what you have learned"],
            "Dear cousin, I saved my pocket money for six months and bought a "
            "blue bicycle last week. I ride it to the park every Sunday with my "
            "friend. I have learned to check the brakes before I ride. "
            "Your cousin, Ismail",
            "Dear cousin,", "Your cousin,"),
    _letter("Your school library needs old books. Write a letter to your "
            "friend to ask him or her for some.",
            ["why the library needs books", "what kinds of books you need",
             "when you will collect them", "how you will thank your friend"],
            "Dear Kumar, our school library needs old books because many pupils "
            "have nothing to read at home. We need storybooks for ages eight to "
            "twelve. Could you bring yours on Saturday? I will "
            "come to your house. Thank you very much. Your friend, Siti",
            "Dear Kumar,", "Your friend,"),
    _letter("You are going to study in Kuala Lumpur next year. Write a "
            "letter to your friend to tell him or her your plan.",
            ["where you will study", "what you will study",
             "why you chose that school", "how you will keep in touch"],
            "Dear Farah, next year I will study at a secondary school in Kuala "
            "Lumpur. I will take science because I want to be a doctor. I chose "
            "that school for its laboratory. I will write to you every "
            "Sunday. Your friend, Sofia",
            "Dear Farah,", "Your friend,"),
    _letter("You found a wallet with money in the school playground. Write a "
            "letter to the owner to return it.",
            ["where you found it", "what was inside",
             "how you can be contacted", "why you want to return it"],
            "Dear Sir or Madam, I found a brown wallet in our school playground "
            "on Monday. It has two ringgit, a driving licence and a card with "
            "the name Lim. Please call me at 012-555 8899. It is not "
            "right to keep other people's things. Your pupil, Daniel",
            "Dear Sir or Madam,", "Your pupil,"),
    _letter("Your class needs a speaker for a school programme. Write a "
            "letter to your teacher to suggest one.",
            ["which programme it is", "who you suggest",
             "why that person is suitable", "how to contact them"],
            "Dear Miss Lim, our school programme on 12 March needs a speaker. I "
            "suggest Mr Tan, our science teacher. He can talk about rainforests "
            "and he brings real leaves for us to touch. You can reach him at "
            "ext. 214. Your pupil, Nadia",
            "Dear Miss Lim,", "Your pupil,"),
    _letter("You helped a pupil who lost her homework. Write a letter to her "
            "teacher to explain what happened.",
            ["what happened", "what the pupil did",
             "how you helped", "what you ask the teacher to do"],
            "Dear Mr Rajoo, Mei Lin lost her homework on the school bus "
            "yesterday. She cried and told me at lunch. I asked her to write it "
            "again at break and I helped her check it. Please let her "
            "submit it late on Wednesday. Your pupil, Farah",
            "Dear Mr Rajoo,", "Your pupil,"),
    _letter("You want to join a school's art club. Write a letter to the "
            "school to ask for a place.",
            ["what you can draw", "why you want to join",
             "when you can attend", "what you promise to do"],
            "Dear Principal, I would like a place in your school's art club. I "
            "can draw animals and I won a district art prize last year. I want "
            "to learn watercolour painting. I can come every Wednesday at three "
            "o'clock. I promise to look after the materials. Yours, Lim "
            "Wei Jian",
            "Dear Principal,", "Yours,"),
    _letter("You are going to a school exchange in another country. Write a "
            "letter to your friend to ask for help with the packing list.",
            ["where you are going", "how long you are away",
             "what you still need to pack", "when you leave"],
            "Dear Sofia, I am going to Japan for a school exchange in July. I "
            "will be away for two weeks. I still need to pack a towel, a "
            "adapter and some medicine. Could you help me buy them? I leave on "
            "the tenth. Your friend, Mei",
            "Dear Sofia,", "Your friend,"),
    _letter("Your neighbour's cat had kittens. Write a letter to your friend to "
            "tell him or her about them.",
            ["how many kittens there are", "what they look like",
             "when you can visit", "what names you chose"],
            "Dear Jun, my neighbour's cat had four kittens on Friday. They have "
            "white paws and they are getting bigger every day. You can see them "
            "on Saturday afternoon. We have named them Cloud, Moon, "
            "Star and Dust. Your friend, Li",
            "Dear Jun,", "Your friend,"),
    _letter("You did badly in a test but learned from it. Write a letter to "
            "your cousin to tell him or her what happened.",
            ["what the test was about", "which question you failed",
             "what you will do differently", "how you feel now"],
            "Dear cousin, I got 42 marks in my science test. I lost eight marks "
            "on the questions about electricity. I did not revise that chapter. "
            "Now I keep a mistake book and I ask my teacher after "
            "class. I am not ashamed any more. Your cousin, Farid",
            "Dear cousin,", "Your cousin,"),
    _letter("You want to sell a homemade cake at a school fair. Write a "
            "letter to your friend to ask if he or she will help.",
            ["what you are baking", "how many cakes you will make",
             "when the fair is", "what help you need"],
            "Dear Aiman, I am baking twelve chocolate cakes for our school fair "
            "on 20 April. Each cake costs three ringgit. I need someone to mind "
            "the table with me from nine to one. Can you help? Please "
            "tell me by Friday. Your friend, Siti",
            "Dear Aiman,", "Your friend,"),
    _letter("Your school will plant a garden for elderly visitors. Write a "
            "letter to your teacher to give your opinion.",
            ["why the garden is a good idea", "what should be planted",
             "who can help", "how it should be cared for"],
            "Dear Miss Ng, I think a garden for elderly visitors is a good idea "
            "because they can walk there. We should plant only fragrant herbs "
            "and non-slip paths. Pupils can water it during recess. I "
            "suggest our class look after it. Your pupil, Farah",
            "Dear Miss Ng,", "Your pupil,"),
    _letter("You are organising a book sale for your class. Write a letter to "
            "your parents to ask for help.",
            ["when the sale is", "where it will be held",
             "what you need from them", "how the money will be used"],
            "Dear Mother and Father, our class book sale will be on 8 March in "
            "the school hall. We need a table, two boxes and help carrying the "
            "books at eight o'clock. All the money will go to the school "
            "library. Thank you. Your daughter, Sofia",
            "Dear Mother and Father,", "Your daughter,"),
    _letter("You watched a documentary about the sea. Write a letter to your "
            "friend to share what you learnt.",
            ["what the film was about", "one fact you remember",
             "what worries the film showed", "what you will do now"],
            "Dear Nadia, I watched a documentary about coral reefs on Saturday. "
            "It said that warm water makes the coral turn white. The film "
            "showed reefs near our coast. I will not throw plastic into "
            "the river now. Your friend, Rafi",
            "Dear Nadia,", "Your friend,"),
    _letter("You want to borrow a book from your school library but it is out. "
            "Write a letter to the librarian to ask about it.",
            ["which book you want", "why you want it",
             "when you need it by", "what you can do if it is still out"],
            "Dear Librarian, I would like to borrow Journey to the River. I "
            "need it for a book report on Monday. It is out until Thursday. "
            "Could you keep it for me, or may I take a photocopy of the first "
            "chapter? Thank you. Farah",
            "Dear Librarian,", "Farah,"),
    _letter("Your class trip to the museum has been changed. Write a letter to "
            "your friend to tell him or her the new plan.",
            ["what the trip was", "what it is now", "the new date",
             "what you must bring"],
            "Dear Jun, our museum trip has changed because of the holidays. It "
            "is now on 12 August instead of 5 March. We will go by coach and "
            "eat lunch at the cafe. Please bring a hat and a water bottle. Your "
            "friend, Ali",
            "Dear Jun,", "Your friend,"),
    _letter("You would like to join the school's swimming club. Write a "
            "letter to ask for permission.",
            ["why you want to join", "what you can do already",
             "when you can practise", "what you promise about lessons"],
            "Dear Mr Chong, I would like to join the swimming club. I can float "
            "and swim twenty metres. I can practise on Wednesday and Saturday "
            "afternoons. I promise to attend every lesson and to tell "
            "you if I cannot come. Your pupil, Daniel",
            "Dear Mr Chong,", "Your pupil,"),
    _letter("You found a wallet and know who it belongs to. Write a letter to "
            "your class teacher to hand it in.",
            ["what the wallet looks like", "what was inside",
             "how you know the owner", "where you found it"],
            "Dear Miss Ho, I found a black wallet near the canteen. It has a "
            "student card for class 3A inside. I know the boy because he is in "
            "my class. I found it after lunch on Tuesday. I will hand it to "
            "the office today. Your pupil, Lim",
            "Dear Miss Ho,", "Your pupil,"),
    _letter("You are organising a class outing to the wet market. Write a "
            "letter to your parents to ask for permission.",
            ["where you are going", "when you are going",
             "what you will learn", "what you need from them"],
            "Dear Mother and Father, our class will visit the wet market on 14 "
            "February to learn about prices. We will leave at eight and return "
            "before lunch. I need ten ringgit for a workbook and a plastic bag "
            "for rubbish. Your son, Daniel",
            "Dear Mother and Father,", "Your son,"),
    _letter("You have a new pen pal in another country. Write a letter to "
            "start the friendship.",
            ["your name and age", "where you live",
             "what your hobbies are", "two questions you ask"],
            "Dear Pen Pal, my name is Mei and I am twelve. I live in Johor "
            "Bahru, Malaysia. I like drawing and playing badminton. What is "
            "your town like? What do you do after school? Your pen pal, Mei",
            "Dear Pen Pal,", "Your pen pal,"),
    _letter("You need a permission slip signed. Write a letter to your parent "
            "to explain the trip and ask for help.",
            ["where the trip is", "when it is", "what you need them to bring",
             "what you need them to sign"],
            "Dear Mother, our class will go to the science centre on 20 May. We "
            "leave at seven in the morning and return at four. I need you to "
            "sign the slip and to pack a packed lunch. Thank you. Your "
            "daughter, Sofia",
            "Dear Mother,", "Your daughter,"),
    _letter("You want to start a recycling box at home. Write a letter to "
            "your father to suggest it.",
            ["what you want to recycle", "where the box will be",
             "how often you will empty it", "what you hope to do with it"],
            "Dear Father, may I put a blue box beside the kitchen door? We can "
            "keep plastic bottles and paper in it. I will empty it every "
            "Sunday. We can sell the bottles and buy things for the school "
            "garden. Your son, Daniel",
            "Dear Father,", "Your son,"),
    _letter("You are writing to a newspaper about a broken street lamp. Write "
            "a letter to the editor to complain politely.",
            ["where the lamp is", "what problem it causes",
             "who is affected", "what you want done"],
            "Dear Editor, the street lamp outside our flats has been broken for "
            "two weeks. It is very dark when we walk home from school. Two "
            "pupils have fallen because of it. Please ask the council to "
            "repair the lamp this month. Yours faithfully, Farah",
            "Dear Editor,", "Yours faithfully,"),
    _letter("Your class lost a sports day match. Write a letter to your friend "
            "to tell him or her how you feel.",
            ["which match you lost", "the final score",
             "how the match went", "what you will do next"],
            "Dear Jun, we lost the football final to 3A by two goals. It was "
            "one all at half time. Our second goal was ruled out for handball. "
            "I felt angry for ten minutes, then I was proud of our team. We "
            "practise on Wednesday. Your friend, Ali",
            "Dear Jun,", "Your friend,"),
    _letter("You want to invite a foreign exchange student to your home. Write "
            "a letter to your teacher to suggest it.",
            ["when the student will come", "what your family can offer",
             "what your home is like", "why you want to help"],
                        "Dear Miss Tan, the exchange student from Finland will stay with us "
            "for one weekend in April. My family can offer a room and home "
            "cooking. We live in a small flat. I want to help because I am "
            "learning about her country too. Your pupil, Mei",
            "Dear Miss Tan,", "Your pupil,"),
    _letter("You noticed your town's playground is unsafe. Write a letter to "
            "the council to ask for repairs.",
            ["what is broken", "who plays there",
             "what could happen", "what you want done first"],
            "Dear Council, the swings in our town playground have a broken "
            "chain. Small children play there every afternoon. Someone could "
            "fall and be hurt. Please repair or remove the swings. We can also "
            "help to keep the playground clean. Yours, a resident",
            "Dear Council,", "Yours, a resident"),
    _letter("You are writing to thank a nurse who helped your mother. Write a "
            "letter to the clinic to say thank you.",
            ["what happened to your mother", "how the nurse helped",
             "how long the nurse stayed", "what you want to say"],
            "Dear Nurse, my mother fell ill at home last month. You came three "
            "times and checked her carefully. You stayed with her until my "
            "father came. She is well now. Thank you for your kindness. "
            "Daniel",
            "Dear Nurse,", "Daniel"),
    _letter("You want your school's recycling programme to start earlier. "
            "Write a letter to your teacher to suggest it.",
            ["when it should start", "which bins you need",
             "how you will help", "what difference you expect"],
            "Dear Miss Ng, may we start the recycling programme in January "
            "instead of April? We need three bins, one for paper, one for "
            "plastic and one for glass. I will make the labels with my art "
            "club. Less rubbish will go to the dump. Your pupil, Farah",
            "Dear Miss Ng,", "Your pupil,"),
    _letter("You are moving house and must say goodbye to your teacher. Write "
            "a letter to thank her or him.",
            ["where you are moving", "how long you were taught",
             "what you will remember", "what you hope for her or him"],
            "Dear Miss Ho, my family is moving to Ipoh on Monday. You taught me "
            "for two years. I will remember the reading corner and your story "
            "about the moon rabbit. I hope your new class loves you. "
            "Thank you. Your pupil, Sofia",
            "Dear Miss Ho,", "Your pupil,"),
]

# ---------------------------------------------------------------------------
# Year 6 Part 7 — longer email, 60 - 80 words
# ---------------------------------------------------------------------------

Y6_LONG = [
    _email("Your class interviewed an old person about life in the past. "
           "Write an email to your friend to report what you learned.",
           ["who you interviewed", "how they lived as a child",
            "how they travelled to school", "what they did after school",
            "what surprised you most"],
           "Dear Wei Lin, My group interviewed Mrs Tan, who is seventy-two. "
           "She said she walked to school for forty minutes because there was "
           "no bus. There was one shop in the village and it sold sweets and "
           "kerosene together. After school she helped her mother and played "
           "in the river. She still cooks curry the old way. What surprised me "
           "most was that she says she was happier then. Your friend, Mei",
           "weilin@email.com", "Life in the Past", long=True),
    _email("You took part in a school debate about school uniforms. Write an "
           "email to your friend to give your opinion.",
           ["the two sides of the debate", "which side you argued",
            "your strongest reason", "a point from the other side",
            "how you felt afterwards"],
           "Dear Aiman, Our class debated school uniforms. One side said "
           "uniforms make us equal and safe. The other said they stop us "
           "showing our personality. I argued for uniforms on school days "
           "only, because clothes cost money and some families cannot buy new "
           "ones every term. Kumar from the other side said uniforms stop "
           "bullying, and that is hard to answer. Our team won. Your friend, Li",
           "aiman@email.com", "Should We Wear Uniforms?", long=True),
    _email("Your class looked after a school garden for a term. Write an email "
           "to your friend to report on it.",
           ["what you planted", "how you split the work",
            "what problems you met", "what you harvested",
            "what you would change next time"],
           "Dear Kumar, My class kept a garden behind the canteen for one "
           "term. We planted spinach, chillies and two mango trees. We split "
           "the work into groups for watering and weeding. Caterpillars ate "
           "the spinach, so we built a net. We harvested six baskets of "
           "chillies and sold them for twenty-four ringgit. Next term I would "
           "start the "
           "nursery first. Your friend, Siti",
           "kumar@email.com", "Our School Garden Report", long=True),
    _email("You went on a three-day school camp. Write an email to your friend "
           "to tell him or her about it.",
           ["where the camp was", "what you did each day",
            "the food and the weather", "something that was scary",
            "what you would bring if you went again"],
           "Dear Farah, our class went to a camp at the coastal village last "
           "week. On the first day we walked the mangrove board walk. The next "
           "day we built a raft and it floated. It rained hard on the last "
           "night and water came under the tent. If I go again I will bring "
           "dry bags and my own torch. I miss the sound of the sea at night. "
           "Your friend, Mei",
           "farah@email.com", "My Three-Day School Camp", long=True),
    _email("You interviewed your grandmother about a traditional craft. Write "
           "an email to your friend to describe it.",
           ["which craft it is", "what it is made from",
            "the steps of making it", "how your grandmother learned it",
            "whether young people still do it"],
           "Dear Sofia, I asked my grandmother about weaving because she does "
           "it every Hari Raya. She uses pandan leaves which she dries first. "
           "She strips the leaves, folds them and stitches them into a "
           "ketupat. She learned it from her grandmother at nine years old. "
           "Few young people know the craft now. I want to learn it before I "
           "forget. Your friend, Daniel",
           "sofia@email.com", "My Grandmother's Weaving", long=True),
    _email("Your class ran a simple experiment about air. Write an email to "
           "your friend to report the results.",
           ["what the experiment was", "the steps you followed",
            "what you observed", "what you concluded",
            "what you would change"],
           "Dear Nadia, Our science group tested how much air a balloon holds. "
           "We filled a bottle, trapped the air with a balloon and measured "
           "the water that came out. The bigger bottle pushed out more water, "
           "so it held more air. We concluded that air takes up space even "
           "though we cannot see it. We would use larger bottles next time. "
           "Your friend, Hafiz",
           "nadia@email.com", "Our Experiment on Air", long=True),
    _email("You joined a service trip to a village school. Write an email to "
           "your friend to tell him or her what you did.",
           ["where the village is", "how you travelled there",
            "what you taught or gave", "what the pupils asked you",
            "how the trip changed your view"],
           "Dear Rafi, our class visited a village school in the hills during "
           "the holiday. The bus ride took four hours. We repainted two walls "
           "and taught Year Four the English alphabet. The pupils asked which "
           "country we came from and what our food tastes like. They were shy "
           "at first but very loud later. I now know how lucky my own school "
           "is. Your friend, Hakim",
           "rafi@email.com", "Our Village School Trip", long=True),
    _email("You are writing about a book you read for a school report. Write "
           "an email to your teacher to give your opinion.",
           ["the title and the author", "the story in a few sentences",
            "which character you liked", "why the book is worth reading",
            "a rating out of five"],
           "Dear Miss Tan, I read a book called Keeper of the Winds by SITI "
           "NORHAZALI for my report. It tells the story of a boy who sails to "
           "a far island to find his father. I liked the captain, who was "
           "strict but fair. The book is worth reading because the sea is "
           "described so clearly that I could smell it. I give it four out of "
           "five. Your pupil, Farah",
           "farah@email.com", "My Book Report", long=True),
    _email("Your school held a week without plastic. Write an email to your "
           "friend to describe it and ask for their help.",
           ["why the week was held", "what pupils had to change",
            "how much waste fell", "what your school did afterwards",
            "one thing you still forget"],
                      "Dear Jun, our school had a week without plastic because our bin "
           "was full of wrappers. We packed food in paper and asked the shop "
           "for no bags. The rubbish weighed eleven kilograms less. Now we "
           "keep the paper habit, but I still forget a straw sometimes. Could "
           "you also stop using straws at your house? It is a small habit, but "
           "it adds up. Your friend, Ali",
           "jun@email.com", "A Week Without Plastic", long=True),
    _email("You attended a talk by a Paralympic athlete. Write an email to your "
           "friend about it.",
           ["who gave the talk", "what happened to her or him",
            "the three things she or he said", "your favourite story",
            "how the talk changed you"],
           "Dear Siti, we had a talk from Nurul Huda, a Paralympic swimmer. "
           "She lost her left arm in an accident at eleven but trained every "
           "single day. She said her coach never let her feel sorry for "
           "herself, her family cheered every race, and pain is only a number. "
           "My favourite story was about finishing a race with one arm. I now "
           "complain less about small things. Your friend, Adib",
           "siti@email.com", "A Talk by a Paralympic Athlete", long=True),
    _email("Your class made a short radio play about a village. Write an email "
           "to your friend to describe the project.",
           ["the story you wrote", "how you divided the work",
            "how you made the sound effects", "what was the hardest part",
            "where the play was played"],
           "Dear Kumar, our group wrote a radio play about a village with no "
           "shop. I wrote the story, three others did the voices and two made "
           "the sound effects with rice and a tin. The hardest part was "
           "recording the market noise without shouting. We played it at the "
           "school hall last Friday and everyone laughed at the tin can. Your "
           "friend, Siti",
           "kumar@email.com", "Our Village Radio Play", long=True),
    _email("You keep a nature journal. Write an email to your friend to share "
           "what you have recorded.",
           ["what you record", "how often you write",
            "the most interesting thing you saw",
            "a change you noticed over time", "what you hope to see next"],
           "Dear Nadia, I keep a nature journal in a small notebook. I write "
           "what I see every Sunday morning: birds, insects, plants and the "
           "sky. The most interesting thing was a heron that stood in the same "
           "spot for three weeks. This year I saw fewer dragonflies than last "
           "year. I hope to see them again when the rains come. Your friend, "
           "Hafiz",
           "nadia@email.com", "My Nature Journal", long=True),
    _email("You think your neighbourhood needs more play spaces. Write an "
           "email to your town council to make your case.",
           ["what is missing in your area", "how many children are affected",
            "where the space could be", "what the space would contain",
            "how the council can find out more"],
           "Dear Council, our neighbourhood has no playground. About two "
           "hundred children live in the flats and they play on the road. One "
           "child was hurt there last year. The empty lot beside the surau can "
           "hold a small playground with a slide and a basketball court. We "
           "have already collected sixty signatures. Please send someone to "
           "look at the lot. Yours, a resident",
           "council@email.com", "We Need a Playground", long=True),
    _email("You took part in a debate about food waste. Write an email to your "
           "friend to give your view.",
           ["the question", "how much food is wasted at home",
            "what your family now does", "one change you would make at "
            "school", "why it matters"],
           "Dear Wei Jian, our class discussed how much food is wasted. My "
           "family used to throw away rice every day. Now my mother cooks less "
           "and we keep leftovers for lunch. I think the school canteen should "
           "sell small portions, because many of us buy a large plate and "
           "cannot finish it. It matters because the money is from our "
           "parents and the food is real. Your friend, Liyana",
           "weijian@email.com", "Is Our Food Waste Too Much?", long=True),
    _email("You learned a traditional song from your grandmother. Write an "
           "email to your friend to tell him or her about it.",
           ["which song it is", "who taught you", "the words it is about",
            "when people sing it", "whether you will teach someone else"],
           "Dear Rafi, my grandmother taught me the song that paddy workers "
           "sang in the fields. It is about planting rice and waiting for "
           "rain. Our family sings it at Hari Raya and at weddings. She "
           "learned it from her sister, who worked in the fields. I have "
           "recorded it on my phone "
           "and I will teach my cousin next month. Your friend, Hakim",
           "rafi@email.com", "A Song from My Grandmother", long=True),
    _email("You are helping to plan a reunion for old school friends. Write an "
           "email to your friend to organise the food.",
           ["when the reunion is", "how many people are coming",
            "what food you suggest", "who will bring what",
            "how people should reply"],
                      "Dear Siti, our class reunion is on 12 October at the community "
           "hall. About forty of us can come. I suggest nasi lemak in the "
           "morning and a buffet at lunch. Our class will bring fruit, while "
           "the other classes bring rice and drinks. Please reply by 20 "
           "September so we can order enough. We still need someone to bring "
           "the tables. Your friend, Daniel",
           "siti@email.com", "Reunion Food Plan", long=True),
    _email("You studied how a simple machine works. Write an email to your "
           "friend to explain what you learned.",
           ["which machine you studied", "which parts it has",
            "how it makes work easier", "an example in your home",
            "a test you did to prove it"],
           "Dear Kumar, we studied the lever in science. A lever has a bar, a "
           "pivot and a load. When the load is far from the pivot, the bar "
           "pushes it up more easily. At home we used a bottle opener, which "
           "is a first-class lever. We lifted a book with a ruler and the far "
           "end needed less force. Your friend, Siti",
           "kumar@email.com", "How a Lever Works", long=True),
    _email("You joined a youth football team. Write an email to your friend to "
           "tell him or her how training is going.",
           ["which team you joined", "how often you train",
            "what your coach asks you to do", "a match you won or lost",
            "what you hope to achieve this year"],
           "Dear Nadia, I joined the MPU Klang youth team last month. We train "
           "three times a week. Coach Rajoo makes us pass twenty times before "
           "we may shoot. We won our first match two nil and lost the second "
           "one. I hope to play in the under-twelve final this year. Last week "
           "I scored twice in training, which is my best so far. My mother "
           "washes my kit every night. Your "
           "friend, Hafiz",
           "nadia@email.com", "My Football Training", long=True),
    _email("You are writing to your future self. Write an email to describe your "
           "goals for next year.",
           ["what you want to achieve", "why it matters to you",
            "the steps you will take", "a habit you will keep",
            "how you will know you succeeded"],
           "Dear Farah, next year I want to be better at two things: swimming "
           "and speaking English. Swimming matters because I want to join the "
           "school relay. I will practise three times a week and ask my coach "
           "about my times. For English I will read for fifteen minutes every "
           "night and speak in English at dinner. I will know I succeeded if "
           "I can swim fifty metres without stopping. Your friend, Sofia",
           "farah@email.com", "A Letter to My Future Self", long=True),
    _email("Your class built a website about your town. Write an email to your "
           "friend to describe it.",
           ["what the website is about", "how you chose the design",
            "what you wrote about", "how you checked the facts",
            "what visitors will see first"],
           "Dear Wei Jian, my group built a website about our town for the "
           "computing fair. We chose a green and white design because the town "
           "is known for its park. I wrote the page about the wet market and "
           "the old temple. We checked every fact with the town office before "
           "uploading. A photo of the market will be the first thing visitors "
           "see. Your friend, Mei",
           "weijian@email.com", "Our Town Website", long=True),
    _email("You went to a talk on safe use of the internet. Write an email to "
           "your friend to tell him or her what you learned.",
           ["who gave the talk", "the dangers they mentioned",
            "what you should do about them", "a rule you will follow",
            "how you will remind your family"],
           "Dear Rafi, a police officer spoke to our class about the internet. "
           "He said people can pretend to be anyone, and they can ask for your "
           "photos or your address. He told us never to meet a stranger alone "
           "and to tell an adult. My new rule is that I check with my mother "
           "before I accept a game request. I will ask my "
           "cousin to do the same. Your friend, Hakim",
           "rafi@email.com", "Staying Safe Online", long=True),
    _email("You are writing to thank a shopkeeper who helped your mother. "
           "Write an email to tell him what happened.",
           ["what your mother needed", "how he helped",
             "how long she was helped", "what the result was",
             "what you want to say now"],
                      "Dear Mr Lim, my mother was stuck outside the shop last Sunday "
           "because her shoe lace broke and she had no spare. You gave her "
           "tape and helped her for fifteen minutes while other customers "
           "waited. She walked home safely and wanted me to thank you. She "
           "often praises you. If you are ever near our street, please drop by "
           "for a drink. Please accept our best wishes. Farah",
           "farah@email.com", "Thank You, Mr Lim", long=True),
    _email("You measured how much water your family uses in a week. Write an "
           "email to your friend to report the results.",
           ["how you measured it", "how much water you used",
            "which activity used the most", "what you changed",
            "what difference it made"],
           "Dear Siti, we tracked our water for a week. I wrote the meter "
           "reading every morning and night. We used three hundred and twenty "
           "litres, mostly for showering and washing. Baths used the most, so "
           "my father now showers instead. This week we used two hundred and "
           "forty litres. Saving water really does lower the bill. We will "
           "keep the chart for a month. Your "
           "friend, Adib",
           "siti@email.com", "Our Family Water Report", long=True),
    _email("You wrote a story for a school magazine. Write an email to your "
           "friend to tell him or her about it.",
           ["what your story is about", "how you planned it",
            "how long you took", "the feedback you got",
            "whether you will write again"],
           "Dear Nadia, I wrote a story for the school magazine called The "
           "Last Mango. It is about a boy who saves the last fruit for his "
           "grandmother. I planned it in five parts and wrote a bit every "
           "evening for two weeks. The editor liked the last line and cut one "
           "joke. I will write again next term. Your friend, Hafiz",
           "nadia@email.com", "My Story in the Magazine", long=True),
    _email("You are comparing two markets in your town. Write an email to your "
           "friend to give your advice.",
           ["which markets you compared", "how they are different",
            "which is cheaper", "which is easier to reach",
            "which one you would choose"],
           "Dear Kumar, my group compared the morning market with the night "
           "market. The morning market sells more vegetables and the prices "
           "are lower. The night market is easier to reach after school and "
           "has cooked food. I would choose the morning market on Sunday "
           "because the fish is freshest. You should go early, before nine "
           "o'clock. Bring a basket and your own bag. "
           "Your friend, Siti",
           "kumar@email.com", "Which Market Should You Choose?", long=True),
    _email("You were a helper at a fun fair for the school fund. Write an "
           "email to your friend to tell him or her about it.",
           ["where the fair was", "which stall you helped at",
            "how much money you raised", "a funny moment",
            "what you would do differently"],
           "Dear Wei Lin, our school fun fair was on Saturday at the school "
           "field. I helped at the cake stall with my cousins. We sold cakes "
           "and cupcakes and raised four hundred ringgit for the library. One "
           "boy dropped a tray of buns and we still ate the ones on the "
           "ground. "
           "Next year I will bake more and label the prices. Your friend, Mei",
           "weilin@email.com", "Our School Fun Fair", long=True),
    _email("You are writing to a younger pupil about how to prepare for a "
           "test. Write an email to give your advice.",
           ["how you prepare a week before", "how you revise the night before",
            "what you eat and drink", "what you do in the test room",
            "one habit you would change"],
           "Dear Sofia, I have taken my tests for three years now. A week "
           "before, I list the chapters and finish one each day. The night "
           "before I only read the summaries and sleep early. In the test room "
           "I read all the questions first and underline the key words. I eat "
           "breakfast, never skip it. If I could change one habit it would be "
           "studying past midnight. Your friend, Daniel",
           "sofia@email.com", "How I Prepare for Tests", long=True),
]

LETTERS = {6: Y6_LETTERS}

ESSAYS = {
    5: {"short": Y5_SHORT, "long": Y5_LONG},
    6: {"long": Y6_LONG},
}
