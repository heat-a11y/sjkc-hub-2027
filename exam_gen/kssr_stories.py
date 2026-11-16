# -*- coding: utf-8 -*-
"""The CEFR-banded KSSR story corpus — the app's only source of Part 3 prose.

Round 17 made the scanned pupil textbook the sole reference, and Round 26
closed the gap where "a CEFR band is not a curriculum": Victorian prose sits
in the right band and still asks a SJK pupil to recognise *velveteen*,
*corkscrew* and *frock*.  The registry that used to feed Part 3 was five
Gutenberg books — Aesop's Fables, Kipling's Just So Stories, the Velveteen
Rabbit, McGuffey and Peter Rabbit — all nineteenth-century English about
kings, camels and rabbits, and none of it in a KSSR theme.  The ladder gate
refused nearly all of it, so Years 1-2 were left with *no* web passage at
all.

This module replaces them.  Every story is written to the KSSR Semakan 2017
DSKP for its year:

* every content word is on that year's ladder or in the familiar everyday
  vocabulary a primary paper assumes (:mod:`exam_gen.dskp`);
* it sits inside the year's CEFR cap and the Part 3 word band
  (:data:`exam_gen.data.PASSAGE_CEFR` / ``PASSAGE_WORD_BAND``);
* it is tagged with the RPT theme it belongs to, so a themed paper can be
  served a passage about the same topic as the rest of the paper;
* it can answer the official five Part 3 questions with on-ladder options.

The corpus ships with the app — nothing is downloaded, so a refresh works
offline and is byte-identical every run, and there is no licence to track.
Wikimedia-Commons photographs remain the only live-network feature.
"""

from __future__ import annotations

#: ``{year: [{"title", "text", "theme", "cefr"}, ...]}``.  Year 4 is a
#: supported year from Round 36 but no Year 4 KSSR stories are held yet, so it
#: draws its passages from the built-in and web corpora like Years 1-3 do.
#: ``theme`` is always a
#: member of ``data.RPT_THEMES[year]``; ``cefr`` is the band the story is
#: written to and never exceeds the year cap.
STORIES: dict[int, list[dict]] = {}


def _add(year: int, entries: list[dict], cefr: str) -> None:
    """Register a year's stories, stamping the band they were written to."""
    for e in entries:
        e["cefr"] = cefr
    STORIES[year] = entries


# ---------------------------------------------------------------------------
# Year 1 — A1, 40-80 words.  Themes: World of Self, Family and Friends,
# World of Stories, World of Knowledge.
#
# Authoring rules (both are checked by the suite, not by eye):
#   * every sentence carries a noun from the animals / people / places / food
#     classes that ``_fact_questions`` blanks, and
#   * each class keeps at least two unused nouns so the three distractors are
#     still available, so a story always fills five Part 3 questions.
# ---------------------------------------------------------------------------
_add(1, [
    {"title": "My Family", "theme": "World of Self, Family and Friends",
     "text": "My name is Aisyah. I am six. I live in Bidor with my family. "
             "My father is a farmer. My mother cooks rice and chicken for us. "
             "I have a sister. Her name is Hana. We play in the garden every "
             "evening. A cake is on the table for her."},

    {"title": "My Friend Mei", "theme": "World of Self, Family and Friends",
     "text": "Mei is my friend. She sits next to me in class. We share one "
             "pencil box. At recess we run near the field. Her mother gives "
             "us a cake each. On Monday we go to the library with Hana. A dog "
             "ran to us in the park."},

    {"title": "Helping at Home", "theme": "World of Self, Family and Friends",
     "text": "Every Sunday I help my mother in the kitchen. We wash the bowl "
             "after lunch. Then I water the flower in the garden. My sister "
             "brings the water from the tap. My mother is a happy woman. My "
             "father reads a paper in the yard. A dog sleeps near the door."},

    {"title": "My Grandparents", "theme": "World of Self, Family and Friends",
     "text": "My grandmother has a hen in her yard. The hen gives us an egg "
             "every morning. My grandfather sits on a chair near the door. He "
             "tells me a story about a mouse. A mouse ran under the bed. My "
             "grandmother gives me bread and milk. I love my grandfather."},

    {"title": "The Cat and the Bird", "theme": "World of Stories",
     "text": "A cat sat on a wall. A bird came to eat the rice. The cat went "
             "to the tree. The bird sat on a branch. The cat sat under the "
             "tree for a long time. Then the bird sang. The cat went home "
             "without the rice."},

    {"title": "The Lost Ball", "theme": "World of Stories",
     "text": "Tom lost his ball in the park. He looked under a chair. His "
             "sister looked near the pond. A dog ran to the tree. Tom ran "
             "after the dog. The ball was behind the bench. Tom took the "
             "ball home. His sister was very happy."},

    {"title": "A Rainy Day", "theme": "World of Stories",
     "text": "It rained on Sunday. A cloud was over our house. We played in "
             "the kitchen. My mother read a book. My brother drew a horse. "
             "Then a bird flew past the door. The sun came out. We ran to "
             "the field for a game."},

    {"title": "The New Friend", "theme": "World of Stories",
     "text": "A new boy came to our class. He had no friend at lunch. Hana "
             "gave him a bun. She gave him milk too. They talked about a "
             "fish. On Friday they went to the park. The boy had a new "
             "friend. Hana had a new friend too."},

    {"title": "The Big Fish", "theme": "World of Knowledge",
     "text": "There is a big fish in a pond. The fish is grey. It has a long "
             "tail. A duck swam in the water near the pond. My uncle caught "
             "a small fish. He put the fish in a bucket. We took the bucket "
             "to the kitchen."},

    {"title": "Fruit We Like", "theme": "World of Knowledge",
     "text": "I like mangoes. I like apples too. My father goes to a market "
             "on Sunday. He buys fruit for the house. We wash the orange in "
             "the kitchen. Then my sister eats the fruit. My mother puts "
             "the fruit in a bowl."},

    {"title": "My Hen", "theme": "World of Knowledge",
     "text": "We have a hen at home. Her name is Puti. The hen is brown. She "
             "is white too. She gives us an egg every morning. My brother "
             "takes the egg to the kitchen. The hen sits on straw in a yard."},

    {"title": "Sun and Rain", "theme": "World of Knowledge",
     "text": "The sun gives light to our house. The sun gives heat to the rice "
             "in a field. Rain comes from a cloud over the market. A boy stood "
             "in the rain near a shop. He wore a hat. His mother gave him "
             "bread and tea. They went home by car."},
], "A1")


# ---------------------------------------------------------------------------
# Year 2 — A1, 45-90 words.  The same three themes, a wider world.
# ---------------------------------------------------------------------------
_add(2, [
    {"title": "Our House", "theme": "World of Self, Family and Friends",
     "text": "We have a house near a shop. There is a kitchen and a bathroom "
             "in the house. My bedroom has a bed and a chair. A doll sits on "
             "the bed. My father works near the bridge. On Sunday we eat rice "
             "in the kitchen. My dog sleeps by the door."},

    {"title": "My Clothes", "theme": "World of Self, Family and Friends",
     "text": "I have a blue shirt and black trousers. My sister has a pink "
             "dress. She wears a red hat. My brother has new shoes. We go to "
             "a market with my mother. She buys an apple for me. I carry the "
             "bag home. A dog sat near the car."},

    {"title": "A Busy Sunday", "theme": "World of Self, Family and Friends",
     "text": "On Sunday I clean my bedroom. My mother is in the garden. My "
             "father is near the car. A car is white and fast. After lunch we "
             "go to a park. I ride my scooter. My sister rides a scooter too. "
             "We play until it is dark."},

    {"title": "My Cousin Comes", "theme": "World of Self, Family and Friends",
     "text": "My cousin came to our house. She is seven. We play with a doll "
             "in the living room. On Sunday we walk to a stream. A fish is in "
             "the water. She can swim well. I can swim a little. She holds "
             "my hand. We go home for lunch."},

    {"title": "The Cat in the Rain", "theme": "World of Stories",
     "text": "A white cat went out in the rain. The rain made her feet wet. A "
             "woman saw the cat near a shop. She took the cat into her "
             "house. She gave the cat some milk. The cat drank the milk. The "
             "cat slept on a chair. The sun came out later."},

    {"title": "The Snowman", "theme": "World of Stories",
     "text": "It was cold one morning. A tree was white with snow. My brother "
             "and I made a snowman in the garden. We gave him a black hat. "
             "We gave him an orange nose. A bird sat on his head. A cat "
             "watched us from a chair by the door. The snowman was very small "
             "at noon."},

    {"title": "The Football Match", "theme": "World of Stories",
     "text": "Our class played a match on Friday. My friend Hana scored the "
             "first goal. A boy on the other team was cross. Mei gave him a "
             "cup of water. A coach stood near the door. The ball went to the "
             "end of the field. A girl ran after it. Our class won by one "
             "goal."},

    {"title": "The Lost Puppy", "theme": "World of Stories",
     "text": "A brown dog ran away from a house. The dog was very young. The "
             "family looked in a park. They looked near a shop too. A boy "
             "found the dog under a bench. He told his teacher. The teacher "
             "called the family. The dog went home in a car."},

    {"title": "The Weather Today", "theme": "World of Knowledge",
     "text": "Today the sun is bright. A bird is in the tree. Yesterday the "
             "weather was cold. A cat sat by the door. In the afternoon there "
             "will be rain. A drop of rain will fall on a flower. My mother "
             "will close the window. My brother will take his ball to the "
             "park. We will stay at home and eat rice."},

    {"title": "A Day at the Beach", "theme": "World of Knowledge",
     "text": "Last Sunday we went to a beach. The sea was blue. My sister "
             "made a castle in the sand. A green shell was near the water. I "
             "put the shell in my pocket. A boat came to the shore. We did "
             "not swim because the waves were big."},

    {"title": "My Piano Lesson", "theme": "World of Knowledge",
     "text": "Every Wednesday I go to a piano lesson with my friend. My "
             "teacher is a kind woman. She plays a song for me. Then I play "
             "the song too. My hands are not long. I press the white keys. A "
             "cat sleeps on my bed at home. My mother waits for me in the "
             "kitchen. My father is at the market now. After one hour my "
             "fingers are tired."},

    {"title": "At the Market", "theme": "World of Knowledge",
     "text": "On Saturday my mother and I went to a market near our house. We "
             "bought chicken and vegetables. We bought a big watermelon too. "
             "The market man gave us two small apples. We had lunch at a shop "
             "near the road. My mother drank a cup of tea."},
], "A1")


# ---------------------------------------------------------------------------
# Year 3 — A2, 50-100 words.  The pupil can hold a main idea across a longer
# text, so these stories carry a small plot while keeping the same
# "every sentence has a blankable noun" discipline.
# ---------------------------------------------------------------------------
_add(3, [
    {"title": "A Busy Morning", "theme": "World of Self, Family and Friends",
     "text": "Every school day I get up at six. I wash my face and eat some "
             "bread with milk. My mother takes my sister and me to school at "
             "seven. A teacher waits at the school gate. I am never late for "
             "class. After school I play football in the field. At night I "
             "read a book before I sleep."},

    {"title": "My Mother's Job", "theme": "World of Self, Family and Friends",
     "text": "My mother is a nurse. She works at a clinic near our house. She "
             "starts early and comes home late. Sometimes she is very tired in "
             "the evening. I help her wash the bowls. My father is a cook in a "
             "small restaurant. He makes noodles for lunch every day. We eat "
             "rice and vegetables at night."},

    {"title": "My New Bike", "theme": "World of Self, Family and Friends",
     "text": "Last month I got a new bike for my birthday. It is red and it is "
             "light. I ride it to the park every Sunday. At first I was afraid "
             "to go down the hill. My friend says we should ride to the lake "
             "together. A shop near my house sells bread and milk. A dog ran "
             "after us on the road."},

    {"title": "A Letter to Grandma", "theme": "World of Self, Family and Friends",
     "text": "My grandmother lives in a village near the sea. A doctor is her "
             "friend. Last week I wrote a letter to her in the kitchen. My "
             "mother helped me. I put a photo in the letter. Grandma wrote "
             "back on Friday. Her pupil read the letter to her. We will visit "
             "her school in December."},

    {"title": "The Clever Crow", "theme": "World of Stories",
     "text": "A crow was thirsty one hot day. He found a tall jug but there "
             "was only a little water at the bottom. The crow put small "
             "stones into the jug one by one. The water came up to the top at "
             "last. The crow drank the cool water. Then he flew away. A cat "
             "watched the crow from a tree."},

    {"title": "A Trip to the Zoo", "theme": "World of Stories",
     "text": "Our class went to the zoo last Friday. We saw a big elephant "
             "and two small monkeys. The monkeys took food from the visitors. "
             "Our teacher said we must not shout at the animals. A lion slept "
             "in the sun all morning. I liked the tiger best. We ate noodles "
             "in the park at lunch."},

    {"title": "The Football Team", "theme": "World of Stories",
     "text": "My school has a football team. I am one of the boys on it. We "
             "practise three times a week in the field. Last month we played "
             "a match in Ipoh. We were one goal down in the first half. In the "
             "second half my friend scored two goals. Our teacher was very "
             "happy. We drank water at the shop after the match."},

    {"title": "The Surprise Party", "theme": "World of Stories",
     "text": "My mother was thirty five last month. My sister and I made a "
             "cake in the kitchen. We put six small candles on it. We asked "
             "my father to bring her into the room. Her friends came at seven "
             "and sang a song. They gave her a present and a big hug. My "
             "brother ate a piece of the cake."},

    {"title": "The Doctor's Visit", "theme": "World of Knowledge",
     "text": "Last Tuesday my brother was ill. He had a high fever and a bad "
             "headache. We took a bus to the clinic. The doctor said he must "
             "drink more water and rest. He gave us some medicine. My brother "
             "ate rice and soup for dinner. He went back to school on Monday."},

    {"title": "Directions to the Library", "theme": "World of Knowledge",
     "text": "Our school library is on the first floor. A girl met me at the "
             "stairs. We went up and turned right at the top. We walked past "
             "the science room. The library is next to the computer room. A "
             "boy was reading a magazine inside. You can borrow two books for "
             "two weeks. My friend waited for me in the hall."},

    {"title": "The Coffee Shop Menu", "theme": "World of Knowledge",
     "text": "The coffee shop near my house has a small menu. A bowl of "
             "noodles costs four ringgit. A glass of tea costs two ringgit. A "
             "waiter works there on Saturday. He says the noodles are very "
             "hot, so we eat them slowly. We drink the tea after lunch at a "
             "table near the door."},

    {"title": "My Dictionary Project", "theme": "World of Knowledge",
     "text": "For our project I must use a new dictionary. My teacher gave me "
             "a book. I looked up the word clever in the library. The "
             "dictionary says it means smart. My friend looked up the word "
             "thin. I wrote five new words in my notebook. A pupil read his "
             "work to the class. My teacher said the project was useful. We "
             "will read our work to the class on Friday."},
], "A2")


# ---------------------------------------------------------------------------
# Year 5 — A2, 80-150 words.  One RPT theme every two stories, so a themed
# paper can be built without repeating a passage.
# ---------------------------------------------------------------------------
_add(5, [
    {"title": "A New Bus Service", "theme": "Towns and Cities",
     "text": "Last year my town had only one bus. The bus came to the market "
             "square twice a day, and people in my street had to walk to it. "
             "Now the town has three buses. One goes to the school, one goes "
             "to the hospital and one goes to the park. My mother takes me to "
             "school on the number six bus. A driver sits near the front door. "
             "The journey to the beach takes about twenty minutes now instead "
             "of a long walk. The council says the new service will make life "
             "easier for old people, because they will not have to carry heavy "
             "shopping on a hot afternoon."},

    {"title": "Our Town Library", "theme": "Towns and Cities",
     "text": "Our town library is in a small building near the school. It "
             "opens at nine in the morning and closes at five in the "
             "afternoon. There are about eight thousand books inside, and a "
             "small computer room at the back. Mr Lim is the librarian. He "
             "helped me find a book about the sea last month. I read it in the "
             "park near the library. A boy from my class comes there every "
             "Saturday to look at the magazines. The town decided to build the "
             "library because the old one was too small for the number of "
             "students in the area."},

    {"title": "The Long Holiday", "theme": "Days",
     "text": "The school holiday is the best part of the year for me. It "
             "lasts about five weeks, from the end of the year until the first "
             "week of January. In the morning I swim at the club. In the "
             "afternoon I help my father in his shop. Every Sunday we visit my "
             "grandfather and eat fish curry with him. On the last day before "
             "school, my friends and I always feel sad. We compare our books "
             "and promise to meet at the library again. I think about the long "
             "days of study when the holiday is over."},

    {"title": "Rainy Afternoons", "theme": "Days",
     "text": "In our town, the afternoon is often the hottest part of the day, "
             "but in the monsoon it is the wettest. When the rain is heavy, we "
             "stay inside the house. My mother teaches my sister to read in "
             "the living room, and I help my grandmother in the kitchen. A "
             "thunder storm can be very frightening for a young child, so we "
             "keep the radio on in the bedroom. On a wet Sunday the whole "
             "family eats lunch together at my aunt's house. I have learned "
             "that a rainy day is not a waste at all, because we are together."},

    {"title": "The Orangutan of Sepilok", "theme": "Wild Life",
     "text": "Sepilok is a small centre in Sabah where rescued apes are cared "
             "for until they can live in the forest again. A baby orangutan was "
             "found in a carton near a town last year. A worker at the centre "
             "gave her milk and a soft blanket. She was very weak for many "
             "weeks, but she slowly became stronger. Today she climbs trees and "
             "eats fruit with the other young apes. The workers say that every "
             "rescued animal gives something back to the forest. Scientists "
             "from many countries come to study the apes, because the species is "
             "now rare in the wild."},

    {"title": "A Bird in the City", "theme": "Wild Life",
     "text": "A large white heron lives in the middle of our town. It stands "
             "in the shallow water of a drain near the market and waits for "
             "fish. Most people in my street now know the bird and leave it "
             "alone. Before the new rubbish bins came, the heron used to hunt "
             "for food in rubbish, which was not healthy for it. Now it catches "
             "real fish in the morning. Last year two other birds built a nest "
             "in a tree behind the school. A biologist from the park came to "
             "look at them. City birds need clean water and quiet places, just "
             "like animals in the forest."},

    {"title": "Our School Garden", "theme": "Learning World",
     "text": "Our science teacher had an idea for the second term. She asked "
             "every class in the school to plant a small garden behind the "
             "building. Our group chose vegetables, because they are easy to "
             "grow and we can see the results quickly. We planted chillies, "
             "beans and sweet potatoes in March. Each group of pupils was "
             "responsible for one row, and we had to write down what happened "
             "every week in a notebook. In June we harvested enough vegetables "
             "to cook a meal for the whole school. The lesson was about "
             "nature, but we also learned that a good experiment needs "
             "patience and careful notes."},

    {"title": "The Reading Challenge", "theme": "Learning World",
     "text": "In March our school started a reading challenge for all pupils. "
             "Every pupil had to read three books before the end of the term "
             "and write a short report about the best one. My teacher gave us a "
             "list of titles in the library, but we could choose any book we "
             "liked. I read a novel about a young sailor, and I also read a "
             "book about the planets. Our class collected more than four "
             "hundred reports. The head teacher said that reading is the only "
             "skill we need in every subject, so she hopes the challenge will "
             "continue next year. I have already borrowed three new books from "
             "the school library."},

    {"title": "Breakfast Is Important", "theme": "Food and Health",
     "text": "Many pupils in my school skip breakfast because they are in a "
             "hurry in the morning. Our health teacher explained what happens "
             "to the body when a person eats nothing before school. Without "
             "food, the brain has no energy, and a pupil cannot concentrate in "
             "the second period. She recommended a simple breakfast with "
             "protein, fruit and water. I changed my routine and now I eat "
             "oats, an egg and a banana before I leave the house. After two "
             "weeks I felt more awake in class. Our school sells healthy food "
             "in the canteen, and a fruit salad costs only one ringgit."},

    {"title": "A Fever at the Clinic", "theme": "Food and Health",
     "text": "Last month my younger brother came home from school with a high "
             "fever. My mother took him to the clinic straight away because "
             "the doctor had told us that a fever must not be ignored. The "
             "symptoms were a headache, a sore throat and a cough. The doctor "
             "said the medicine must be taken at the correct hours, and she "
             "warned us that too much medicine is also dangerous. He stayed in "
             "bed for three days and drank plenty of water. A week later he "
             "returned to school. The clinic gave our family a leaflet about "
             "colds and the danger of taking an old prescription."},

    {"title": "The School Tournament", "theme": "Sport",
     "text": "Our school held a football tournament in August, and every class sent a team of players. My team played three matches on the same field. We lost the first match by one goal, but the coach told us to keep our heads up. In the second match our goalkeeper saved two penalties, and we won. The final was exciting until the last minute. A player on our team injured his leg and had to leave the field. Even without him, we won the trophy by two goals. The important thing I learnt was that a team sport is about supporting each other."},

    {"title": "Swimming Every Morning", "theme": "Sport",
     "text": "My cousin started swimming lessons at the club last year, and she is now in the school team. She swims in the pool every morning before breakfast. The training is hard. Her coach is very strict about safety, so she must count every stroke and never swim alone. Last month she swam in a competition in another town. My mother and my brother went to watch her. She was nervous before the race, but she finished third. A friend from her class went too. Swimming has made her much stronger."},

    {"title": "When I Was Five", "theme": "Growing Up",
     "text": "I do not remember much about when I was five. My mother keeps old photographs in a box at home. In one picture I am standing in front of a shop with my father, and I am holding a toy car. My grandmother says I was a shy child who spoke very little. Last year I moved to a new school in another town, and I was afraid for a week. Now I have eleven classmates and I play football with them every break. My new teacher says I am much braver than before. Growing up has not been easy, but a new place is not terrible if you are brave enough to speak first."},

    {"title": "Helping My Grandfather", "theme": "Growing Up",
     "text": "My grandfather is seventy eight this year, and he is a retired "
             "teacher. He lives alone in a village about an hour from our "
             "house. We visit him every two weeks, and the work is always the "
             "same. He wants the grass cut, the fence checked and the house "
             "cleaned. When I was younger I thought it was boring, but now I "
             "understand that he cannot do these things easily any more. He "
             "tells me stories about his school days while we work in the "
             "garden. I have learned to cook two simple dishes as well, so I "
             "can cook for him when my parents are busy. He says that having "
             "somebody to talk to is the best medicine for an old person."},

    {"title": "Leaving for Overseas", "theme": "Going Away",
     "text": "My elder sister finished school last year, and in January she "
             "will leave for Australia to study. She is packing now, and our "
             "house is full of boxes. She is excited, but my mother cries "
             "whenever she talks about it. My sister promises to call us every "
             "week and to send photographs of her university. I will have to "
             "share a bedroom with my little brother after she goes, and I am "
             "not looking forward to that. Still, I know the trip will give her "
             "a better future. Our family will save enough money for her "
             "flight, and I will help her pack until the last day."},

    {"title": "A Trip to the Island", "theme": "Going Away",
     "text": "During the last school holiday, our family went to an island "
             "about four hours away by car. We stayed at a small hotel near "
             "the beach, and we spent most of the days in the water. On the "
             "first morning my father hired a boat, and a fisherman took us to "
             "see a turtle. We also walked through a village where the people "
             "sell dried fish and coconut. On the last day the sea was very "
             "rough, so we could not swim. I was sad to leave, but I took many "
             "photographs. Travelling teaches you that the world is much "
             "bigger than one small town."},
], "A2")


# ---------------------------------------------------------------------------
# Year 6 — B1, 90-150 words.  Ten RPT themes, two stories each.  This is the
# band JSU asks for at Part 1-5 (a longer text the pupil reads for detail and
# for an opinion), so these texts carry an argument or a problem to solve, not
# just a list of facts.
# ---------------------------------------------------------------------------
_add(6, [
    {"title": "The Fire at the Warehouse", "theme": "It's an Emergency",
     "text": "The fire started in a warehouse near our school on a windy "
             "afternoon. A worker smelled the smoke and called the emergency "
             "number. Firefighters arrived in four minutes, but the wind pushed "
             "the flames towards two houses, so the officer ordered every "
             "family on that road to leave at once. My mother took my sister "
             "to the community hall, where volunteers were already helping "
             "old people. A policeman closed the road and turned the buses "
             "around. Nobody was hurt, but the air smelled of chemicals for "
             "days. The shopkeeper said the lesson is simple: a fire extinguisher "
             "on every wall and a clear emergency route save more lives than "
             "any new machine."},

    {"title": "Floods in the Village", "theme": "It's an Emergency",
     "text": "During the monsoon our village was flooded for nine days. The "
             "river rose faster than usual, and the water reached the second "
             "step of our house. Volunteers from a neighbouring town arrived "
             "with boats and food. The headman used a loudspeaker to tell "
             "people which road was still safe. An old man refused to leave "
             "his farm until his goat was carried to the high ground, and a "
             "rescue worker did it for him. Afterwards the district gave each "
             "family a small payment. The government also promised to build a "
             "wall, but the engineer explained that a wall alone will not stop "
             "a flood; the people must keep the drain clear and move early when "
             "the warning comes."},

    {"title": "The Night the Lights Went Out", "theme": "It's an Emergency",
     "text": "Last year a storm broke the power line and the whole town had no "
             "electricity for two days. The shops closed early, and the lights "
             "in the street were dark. A generator ran the hospital, and the "
             "doctor asked every clinic to send her patients who needed "
             "medicine. The water supply stopped too, so a soldier "
             "distributed water from a truck. Neighbours shared food, and one "
             "family cooked for thirty people in their kitchen. The next "
             "morning a technician came from the capital and repaired the line. "
             "Since then the town hall has kept a small emergency plan, "
             "because everyone remembers how helpless it felt in the dark."},

    {"title": "Life in the Old Kampong", "theme": "Life in the Past",
     "text": "My grandmother grew up in a wooden house on stilts near a river "
             "in Kedah. There was no electricity, so she studied by the light of "
             "a lamp. She walked two kilometres to school every day, and her "
             "school had only one teacher for six classes. Her family grew rice "
             "and fish, and they ate what they grew. Money was rare, so "
             "neighbours exchanged work instead. She still remembers the "
             "passing of a boat seller every morning and the sound of the "
             "cockerels at dawn. She moved to the town in 1978, when a factory "
             "offered her father a job. She says life was harder, but people "
             "knew every neighbour and nobody in the village went hungry."},

    {"title": "Grandfather's Radio", "theme": "Life in the Past",
     "text": "My grandfather repaired radios in a small shop in Ipoh for "
             "forty years. In the 1970s almost every house in the street had a "
             "radio, and the whole family listened to the news at eight "
             "o'clock. He tells me that people also queued outside his shop "
             "during the floods of 1971, because the radio told them where the "
             "food was. He never threw away a broken set; a wooden box with "
             "wires inside could be saved. Today almost every house has a "
             "phone, and nobody asks him to repair anything. He still keeps his "
             "tools in a wooden box, and once a month he goes to the market to "
             "buy a small radio for himself."},

    {"title": "Into the Forest", "theme": "Adventure Time",
     "text": "During the last school holiday, four of us walked into the "
             "forest behind my village with a teacher and two adults. We "
             "carried food for two days, a map, a compass and a plastic bag for "
             "the rubbish. On the first night the rain came, so we built a "
             "shelter under a large tree and kept a fire going. In the morning "
             "we found a stream and followed it down, as the teacher had "
             "explained. On the second afternoon we reached a small "
             "waterfall. A boy slipped on a rock and cut his arm, and the guide "
             "cleaned the wound and tied a bandage. Our adventure taught us "
             "that planning and care matter more than speed in the forest."},

    {"title": "The Cave Rescue", "theme": "Adventure Time",
     "text": "Three experienced climbers entered the limestone cave at nine in the morning, because a storm was expected in the afternoon. A guide and two rescuers stayed at the entrance with a rope and two radios. Half way through, one climber twisted his ankle on the wet steps. He could not walk, so the others tied a rope to a large stone. One rescuer climbed back to the entrance and called for help. A team reached the cave within an hour. They carried the injured climber out on a stretcher. The whole operation was slow and calm, and nobody took a risk. The lesson for us is that an adventure is only worth having if the team can bring every member home."},

    {"title": "A Vet in the Village", "theme": "Cool Jobs",
     "text": "There is no animal hospital in my village, so we have a vet who "
             "travels in an old van. Her job begins at five in the morning. She "
             "treats cows, goats and chickens on farms, and she gives free "
             "advice to families with a sick pet. Most of her work "
             "stops a sick animal from getting ill. She gives injections, "
             "checks the water and teaches farmers to keep the animal house "
             "clean. Last year she found a "
             "disease in one village and saved hundreds of chickens by treating "
             "them in a single week. She says the best part of the job is not "
             "the operation but the moment a farmer thanks her. She wants to "
             "open a small clinic in the town, and she is saving money for it."},

    {"title": "The Man Who Designs Bridges", "theme": "Cool Jobs",
     "text": "My uncle is a civil engineer, and he has designed three small bridges in this state. He sits at a desk with drawings, but he also visits the site every month with a worker and a driver. He says the most important part of his job happens before the first block is laid: he must understand how much water the river can hold in a storm. Once a bridge he designed was damaged by floodwater, and he redesigned the supports. He now teaches a course one day a week, because he believes an engineer must explain ideas to ordinary people, or the bridge will never be finished."},

    {"title": "How a Bicycle Is Made", "theme": "How Is It Made?",
     "text": "A bicycle begins in a small factory that buys steel from a mill. "
             "The workers cut the metal tubes and bend them into a frame. A "
             "different factory makes the two wheels, and a third one makes the "
             "seat and the handle. The parts are not made in one place, because "
             "each factory is good at one job. The parts travel in a truck to a "
             "shop, where a worker fits them together and tightens every screw. "
             "The shop must test the brakes before the bicycle is sold. Making "
             "one bicycle takes about fifty workers in three countries, and it "
             "is cheaper for a shop to buy the parts than to make them itself."},

    {"title": "The Bread Factory", "theme": "How Is It Made?",
     "text": "Bread is one of the simplest foods to make, and yet it needs care. A factory buys flour from a farm, yeast from a laboratory, and salt from a mine. A worker in the factory checks every machine at six in the morning. The flour is kept in a dry room, and a machine mixes it with water, yeast and a little sugar. The dough is left to grow for about an hour. Then a worker cuts each piece of dough and puts it in an oven. Finally the bread is cooled on a rack before it is packed, because bread that is wrapped while hot becomes wet."},

    {"title": "The Song from the School", "theme": "Music and Song",
     "text": "Our school choir sang a folk song at the state contest in July, "
             "and we did not win, but the experience was worth it. The song was "
             "about a fisherman, and the melody came from my grandmother's "
             "village. Our music teacher changed the arrangement completely, because "
             "the older pupils sang the main tune while the younger ones "
             "clapped a rhythm on a coconut shell. At first the two parts did "
             "not fit together, and we practised for eight weeks. On the day, "
             "the audience clapped in time with us. The judge said our "
             "harmony was better than last year. Now the school plays the song "
             "at every assembly."},

    {"title": "The Guitar Lesson", "theme": "Music and Song",
     "text": "My cousin began a guitar lesson at the age of nine, and at first he hated it. His teacher told him to play one note every day for a month, and nothing else. His mother paid for the lesson at a music shop in town. He practised in the corner of the house after school while his sisters watched television. Last month his band played at a small shop opening, and they were paid for the first time. His friend plays the drum and his cousin sings. He says the lesson taught him that a skill is built by boring days."},

    {"title": "The Story of the Bamboo", "theme": "Tell Me a Story",
     "text": "Long ago, a bamboo grove stood beside a village in the north. A "
             "poor farmer cut bamboo every week and sold it at the market, and "
             "he was never satisfied. One day he met an old woman who asked him "
             "why he always cut the young bamboo. He said that the market paid "
             "more for long bamboo. The old woman told him to wait a year and "
             "watch one plant. He laughed, but he watched it. The bamboo grew "
             "taller than his house, and in the market a buyer paid double for "
             "it. From that day the farmer sold only mature bamboo, and his "
             "family became the richest in the village. His neighbours never "
             "knew why his house was full of money."},

    {"title": "The Fisherman's Son", "theme": "Tell Me a Story",
     "text": "A fisherman who lived on a small island caught one fish a day, "
             "and he gave the biggest one to his son. The boy asked why the "
             "father kept the small fish. The fisherman said that a big fish "
             "today can feed the family for a day, but a small fish left in "
             "the sea can become a big one tomorrow. The boy did not believe "
             "him, so he asked his father to throw the small fish back every "
             "day. Years later, when a storm destroyed the other boats, the "
             "family caught one very big fish in the sea, because the boy had "
             "never taken a small one."},

    {"title": "Should School Start Later?", "theme": "What's Your Opinion?",
     "text": "Some parents in my town want the school day to start at nine "
             "instead of seven. Their argument is that pupils who sleep less "
             "are not able to concentrate in the first period. Others think the "
             "change would cause problems for families and for the school bus. "
             "In my opinion, the eight o'clock start is a fair answer. Most "
             "pupils in my class sleep about seven hours, and that is still not "
             "enough. A longer morning of study would not make them learn more, "
             "and it would take away an hour for sport. I would rather see the "
             "school teach pupils how to sleep early, because that habit helps "
             "them for the rest of their lives."},

    {"title": "Is Homework Useful?", "theme": "What's Your Opinion?",
     "text": "A survey in my school found that pupils spend about three hours "
             "on homework every week. Some teachers believe this is necessary, "
             "because practice makes a skill automatic. Others say that too "
             "much homework leaves no time for sport, family or sleep, and a "
             "tired pupil learns very little. I agree with the second group. "
             "Homework is useful when it is short and connected to what we did "
             "in class. It is not useful when a pupil copies forty questions "
             "that the teacher will never mark. I suggest a rule of twenty "
             "minutes for younger pupils, with a subject chosen by the pupil "
             "each night."},

    {"title": "The Missing Bicycle", "theme": "It's a Mystery!",
     "text": "On Monday morning a bicycle was missing from the school rack, and "
             "it belonged to the caretaker. He was sure that nobody had taken "
             "it, because the gate was locked all night. The head teacher asked "
             "every class to help. A girl remembered that a stranger had asked "
             "the pupils the way to the market on Friday. A boy had seen a man "
             "with a ladder near the fence. The police came and looked at the "
             "footprints in the flower bed. On Tuesday a farmer brought the "
             "bicycle back. A man had hidden it in his shed because he wanted "
             "to ride it, and he was ashamed to say so. The caretaker did not "
             "punish him, but he asked him to work in the garden for a month."},

    {"title": "The Light in the School", "theme": "It's a Mystery!",
     "text": "For three weeks a light was seen in the old science block at "
             "night, although the building has been locked since the new school "
             "opened. The caretaker checked the windows every evening and saw "
             "nothing. A group of pupils decided to wait behind the wall, and "
             "at about eleven o'clock they saw a man with a torch. He was not a "
             "thief. He was an old teacher who had taught science there for "
             "thirty years, and he came every week to look at the cupboard where "
             "his old specimens were kept. The school gave him the key, and "
             "he now shows the specimens to pupils once a month."},
    {"title": "The New Bus Route", "theme": "Getting Around",
     "text": "Last month the town started a new bus route for the villages along "
             "the river. Before this, the only transport was a lorry that came "
             "twice a week, and most families had to walk to the main road. The "
             "bus leaves the terminal at six in the morning and reaches the last "
             "village at nine. A driver and a conductor collect the ticket from "
             "each passenger. The journey takes about fifty minutes, but the "
             "village is now connected to the hospital and the market. An old "
             "woman in my village can finally keep her monthly appointment with "
             "the doctor. The operator says the route will only continue if "
             "enough people use it every day."},

    {"title": "Cycling to School", "theme": "Getting Around",
     "text": "My father used to drive me to school every day, and the journey "
             "took twenty minutes in heavy traffic. Two years ago he started "
             "cycling instead, and last year I asked to come with him. We leave "
             "at ten to seven and take the path behind the market, which is "
             "almost free of cars. I ride beside a friend from my class, and we "
             "arrive before the bell. Cycling is cheaper, and it is also better "
             "for the air in our town. On rainy days we simply take the bus, "
             "because safety comes first. My father says the best journey is "
             "the one a person is happy to repeat every day."},
], "B1")

