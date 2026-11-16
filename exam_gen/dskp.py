# -*- coding: utf-8 -*-
"""DSKP vocabulary gate for Parts 1, 2 and 5.

The official SJK papers only ever test words a pupil has met in class.  The
KSSR Semakan 2017 DSKP word list (bundled in :mod:`exam_gen.dskp_words`) is
that contract: Year 3 lists ``pilot, dentist, firefighter, nurse, chef`` and
nowhere near it ``civet``, ``gecko`` or ``tapir``.

Left ungated, the Part 5 word box and the Part 1 short-text distractors drift
into trivia a child has no way to have met.  This module is the single place
that decides whether a word is on-curriculum for a year, so the question
banks, the QC watchdog and the test suite all agree.

Three ideas, deliberately separate:

* :func:`in_list` — the strict test: is this headword in the year's DSKP?
* :func:`allowed` — the practical test: the DSKP, plus function words and the
  closed vocabularies every primary paper relies on (numbers, days, school
  proper nouns).  Used to police *distractors*, which must be familiar even
  when the target is a DSKP noun.
* :func:`off_list` — the audit: which words in a built pool are off-list, so
  a round can report what it pruned instead of silently dropping items.
"""

from __future__ import annotations

import re

from .dskp_words import WORDS

# ---------------------------------------------------------------------------
# The strict per-year list, plus the cumulative ladder.
#
# DSKP lists are cumulative in practice: a Year 6 paper may test a Year 1 word
# (an "aunt" is still a Year 6 word), so the gate looks at the year *and every
# year below it*.  Year 4 is absent from ``WORDS`` (the school skips it), which
# is why the ladder is built from the years that are actually present.
# ---------------------------------------------------------------------------

_PRESENT = tuple(sorted(WORDS))


def _ladder(year: int) -> frozenset:
    """Every DSKP word a pupil may know by the end of ``year``."""
    year = int(year)
    acc: set = set()
    for y in _PRESENT:
        if y <= year:
            acc.update(WORDS[y])
    return frozenset(acc)


LADDER = {y: _ladder(y) for y in (1, 2, 3, 4, 5, 6)}

_WORD = re.compile(r"^[a-z][a-z'\-]*$")


def normalise(word: str) -> str:
    """Lowercase, strip, and take the first token of a phrase.

    ``"T-shirt"`` -> ``"t-shirt"``, ``"live  room"`` -> ``"live"``, ``"padi."``
    -> ``"padi"``.  Multi-word entries in the DSKP (a two-word noun) are
    indexed under their head noun, which is the token a question actually
    blanks out.  A hyphen counts as a token break, so a compound is read by
    its first part: ``"clean-up"`` -> ``"clean"``.
    """
    w = re.sub(r"[^a-z'\- ]", " ", str(word or "").lower())
    w = re.sub(r"[\s\-]+", " ", w).strip()
    return w.split(" ")[0] if w else ""


def _stems(w: str) -> list[str]:
    """``w`` plus the plain forms a pupil would also recognise.

    The DSKP lists headwords, but papers test inflected forms: ``books`` is
    ``book``, ``goats`` is ``goat``, ``chopsticks`` is ``chopstick``, and
    ``feed / feeds / feeding`` are all ``feed``.  Without this, a plural in a
    perfectly ordinary option reads as off-curriculum, which would push the
    gate toward a meaningless word list.
    """
    out = [w]
    # Possessives are the noun plus a clitic, not a different word:
    # "father's" is "father" for curriculum purposes, and a blanked option
    # keeps the clitic ("the cat's toy"), so strip it before suffix work.
    if len(w) > 3 and (w.endswith("'s") or w.endswith("s'")):
        base = w[:-2] if w.endswith("'s") else w[:-1]
        if base not in out:
            out.append(base)
    for suffix, repl in (("ies", "y"), ("ches", "ch"), ("shes", "sh"),
                         ("sses", "ss"), ("xes", "x"), ("zes", "z"),
                         ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if w.endswith(suffix) and len(w) - len(suffix) >= 2:
            cand = w[: -len(suffix)] + repl
            if cand not in out:
                out.append(cand)
    # consonant + y: "study" -> "studied / studying", "fly" -> "flew" is
    # irregular and not handled, but -ied/-ying are regular enough to matter.
    for suf, repl in (("ied", "y"), ("ying", "y")):
        if w.endswith(suf) and len(w) - len(suf) >= 2:
            cand = w[: -len(suf)] + repl
            if cand not in out:
                out.append(cand)
    # Comparatives and superlatives of an adjective: "bigger" is "big",
    # "fastest" is "fast".  Without this the gate read every -er/-est word as
    # a new item, which pushed a Year 5 story about a quick fox off-ladder.
    for suf in ("er", "est"):
        if w.endswith(suf) and len(w) - len(suf) >= 2:
            cand = w[: -len(suf)]
            if cand not in out:
                out.append(cand)
            if cand.endswith("e") and cand[:-1] not in out:
                out.append(cand[:-1])
            if len(cand) > 2 and cand[-1] == cand[-2] and cand[:-1] not in out:
                out.append(cand[:-1])
    # Past tense of a silent-e verb drops only the d: "scored" is "score",
    # "liked" is "like", "walked" is "walk" -- not "scor" / "lik" / "walk".
    if w.endswith("ed") and len(w) > 3 and w[-2] == "e":
        if w[:-1] not in out:
            out.append(w[:-1])
    # -ally -> -al: "automatic" -> "automatically"; plain -ly -> stem.
    if w.endswith("ally") and len(w) > 5:
        cand = w[:-4]
        if cand not in out:
            out.append(cand)
    elif w.endswith("ly") and len(w) > 4:
        cand = w[:-2]
        if cand not in out:
            out.append(cand)
    for suf in ("ing", "ed"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            stem = w[: -len(suf)]
            if len(stem) > 2 and stem[-1] == stem[-2]:
                if stem[:-1] not in out:
                    out.append(stem[:-1])
            # -ing -> -ate: "investigating" is "investigate" plus the
            # dropped silent e.  Restoring it lets the gate see the headword
            # a pupil actually met in class.
            if suf == "ing" and len(stem) > 3:
                cand = stem + "e"
                if cand not in out:
                    out.append(cand)
    # Round 26: the regular rules above cannot see an irregular form, so the
    # gate called "the boy *wrote* to his teacher" off-curriculum because
    # "write" is never reached.  These are the verbs a primary passage uses
    # most; each maps back to the headword the DSKP lists.
    base = _IRREGULAR.get(w)
    if base and base not in out:
        out.append(base)
    return out


#: Irregular verb forms a Years 1-6 passage actually prints, mapped to the
#: DSKP headword.  Deliberately short: only forms that appear in a primary
#: reading text, so the gate stays a vocabulary contract and not a lexicon.
_IRREGULAR = {
    "was": "be", "were": "be", "been": "be", "am": "be", "is": "be",
    "are": "be", "had": "have", "has": "have", "did": "do", "does": "do",
    "done": "do", "went": "go", "gone": "go", "goes": "go",
    "came": "come", "saw": "see", "seen": "see", "made": "make", "took": "take",
    "taken": "take", "gave": "give", "given": "give", "got": "get",
    "found": "find", "told": "tell", "said": "say", "knew": "know",
    "known": "know", "thought": "think", "brought": "bring", "bought": "buy",
    "caught": "catch", "taught": "teach", "fought": "fight", "sought": "seek",
    "wrote": "write", "written": "write", "read": "read", "ran": "run",
    "sat": "sit", "stood": "stand", "lay": "lie", "led": "lead",
    "grew": "grow", "grown": "grow", "drew": "draw", "drawn": "draw",
    "flew": "fly", "flown": "fly", "swam": "swim", "sang": "sing",
    "sung": "sing", "drank": "drink", "drunk": "drink", "ate": "eat",
    "eaten": "eat", "broke": "break", "broken": "break", "chose": "choose",
    "chose": "choose", "chosen": "choose", "spoke": "speak",
    "spoken": "speak", "stole": "steal", "stolen": "steal", "wore": "wear",
    "worn": "wear", "fell": "fall", "fallen": "fall", "fed": "feed",
    "flew": "fly", "froze": "freeze", "lost": "lose", "met": "meet",
    "paid": "pay", "put": "put", "read": "read", "rode": "ride",
    "ridden": "ride", "rose": "rise", "risen": "rise", "shook": "shake",
    "shot": "shoot", "shut": "shut", "slept": "sleep", "spent": "spend",
    "stole": "steal", "swore": "swear", "threw": "throw", "thrown": "throw",
    "understood": "understand", "woke": "wake", "wore": "wear", "won": "win",
    "kept": "keep", "left": "leave", "felt": "feel", "held": "hold",
    "heard": "hear", "hid": "hide", "hurt": "hurt", "laid": "lay",
    "lent": "lend", "lit": "light", "meant": "mean", "sent": "send",
    "built": "build", "burnt": "burn", "dealt": "deal", "dug": "dig",
    "fought": "fight", "rang": "ring", "sank": "sink", "slept": "sleep",
    "sped": "speed", "spun": "spin", "stuck": "stick", "swung": "swing",
    "torn": "tear", "wept": "weep", "wound": "wind",
}


def in_list(word: str, year: int) -> bool:
    """True when ``word`` is an official DSKP headword for ``year`` or below."""
    w = normalise(word)
    if not w or not _WORD.match(w):
        return False
    ladder = LADDER.get(int(year), frozenset())
    return any(s in ladder for s in _stems(w))


def off_list(word: str, year: int) -> bool:
    """Inverse of :func:`in_list` — the word is off-curriculum for the year."""
    return not in_list(word, year)


# ---------------------------------------------------------------------------
# Distractor vocabulary.
#
# A distractor only has to be *familiar*, not on the DSKP: Years 1-2 items
# offer "car / bus / taxi" as options and only one appears in a list.  So the
# distractor gate is a separate, looser vocabulary, and it is what keeps
# option (b) from being a Sanskrit-grade word a pupil cannot reject.
# ---------------------------------------------------------------------------

FUNCTION = frozenset("""
a an the and or but of to in on at by for with from as is are was were be
been am do does did will would shall should can could may might must have
has had this that these those i you he she it we they me him her us them
my your his its our their there here what when where who why how which
not no yes very too so also then than about into out up down off over
under again once always never sometimes often usually
some any each every few many most much more less least near behind beside
between during without until while though although whether both either
neither another other others own only just still already yet ever almost
enough several well rather above below outside inside along around across
per since well instead perhaps maybe well apart
# Clitics and stray fragments a tokeniser can hand us: the possessive in
# "the 1970s", the "s" of "Grandfather's", the apostrophe of "teachers'".
s d ll m re ve t
""".split())

# Closed vocabularies: safe in any year, never "off-curriculum".
CLOSED = frozenset("""
one two three four five six seven eight nine ten eleven twelve thirteen
fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty
fifty hundred first second third fourth fifth last next
monday tuesday wednesday thursday friday saturday sunday
january february march april may june july august september october
november december
morning afternoon evening night today tomorrow yesterday weekend
""".split())

# Proper nouns the official papers use as familiar referents.  Capitalised in
# a question, lowercased here.
PROPER = frozenset("""
malaysia malaysian malay chinese malayalam tamil india indonesia
singapore thailand jakarta kuala lumpur penang johor kedah perak
melaka malacca selangor sabah sarawak terengganu kelantan negeri
pahang perlis labuan putrajaya
lrt ktm rapid kl sentral brickfields chinatown petronas twin towers
batu caves genting malacca strait bidor cameron highlands
masjid surau sk smk
""".split())

#: Pupil and teacher names the official papers actually print.  A reading
#: passage needs a character to ask questions about ("Normalha put the book
#: on the table" -> who?), and a name is not a vocabulary item a pupil is
#: asked to spell, so it belongs with the other familiar referents rather
#: than on the ladder.  Deliberately the common Chinese, Malay and Indian
#: SJK pupil names the exam papers use, in both spellings they appear in.
NAMES = frozenset("""
aisyah nurul aminah syafiq nor rafiq hani din siti salmah ali ahmed
roslan zainab khairul farsi normalha fiona liam daniel syafiqie amir hana
mei tom jack sarah emily sophie arthur ben jasmin jasmine nabila azlan
izwan aqil kamil irfan shahrul norliza kamariah zuraidah liang junxiang
weiling weiyun munchee chiew jia min kai yee ling chee kee meng
lim chong chan wong ng lee tan ong teh chin hock ooi low
jun hau jun hui wee khai puti
""".split())

PROPER = PROPER | NAMES

# Local Malaysian vocabulary the official papers use as familiar referents even
# though the English DSKP word list does not enumerate it: the Y5 official
# Part 3 offers "nasi lemak, char kuey teow and fried noodles" as a
# distractor, and the Y1 papers test "nasi lemak / satay / roti canai".
# English-medium SJK pupils meet these daily, so treating them as off-list
# would reject authentic paper language.
LOCAL = frozenset("""
nasi lemak satay roti canai kuih laksa char kuey teow mee goreng
nasi goreng teh tarik roti telur satay ayam ikan goreng
cempedak durian rambutan mangga betik pitaya
milo teh tarik kopi ais sirap bandung
basikal kereta bas kapal kereta api kapal terbang
""".split())

# Common everyday nouns the DSKP assumes without listing (per the DSKP's own
# "familiar topic" framing).  Deliberately short: a word not on the DSKP and
# not here is a real finding, not noise to be suppressed.
EVERYDAY = frozenset("""
mum mom mother dad father parent parents brother sister cousin uncle aunt
postman postwoman garbage rubbish bin dust sweep clean wash
trousers shirt shoes socks hat scarf dress skirt shorts
balloons envelopes crayons pencils rubbers sharpeners
vegetables biscuits sandwiches sausages cheese burgers
towels soap shampoo toothbrush comb mirror
window curtains sofa cupboard shelf lamp clock poster
balloon kite scooter roller skates pogo
beach sandcastle shells bucket spade
postcard stamp envelope address
umbrella jacket sweater gloves
traffic light pedestrian crossing bridge tunnel
lighthouse windmill fountain statue
sunny cloudy rainy windy snowy
quickly slowly loudly quietly carefully
suddenly finally usually sometimes always
grandma grandma grandfather family friend friends name class pupil pupils
teacher boy girl children child baby man woman people
home house room kitchen bedroom bathroom garden yard door window wall floor
chair table bed desk sofa
water milk tea juice rice bread egg cake biscuit chocolate
apple banana orange mango fruit meat chicken fish vegetable soup noodles
bus car van taxi train plane boat bicycle bike motorbike lorry ship
shop market supermarket mall cafe cinema hospital clinic library park
zoo beach playground swimming pool stadium field court
happy sad angry tired hungry thirsty ill sick fine good bad big small tall
short long fat thin old new young hot cold clean dirty fast slow loud quiet
happy bright dark blue red green yellow black white brown pink purple
grey orange
today tomorrow yesterday now then always never sometimes
week weekend holiday day night morning afternoon evening
mum dad brother sister family friend
paper pencil book bag pen ruler eraser crayon desk chair
cat dog bird fish rabbit chicken mouse frog
play run jump swim walk sing dance read write draw ride climb
help cook clean wash brush watch listen speak talk
put place set keep carry bring take give show tell ask answer
cut chop pour boil fry mix add fill empty pour
grow plant water feed raise care look after
build make create draw paint colour cut
move stop start begin end finish wait stay leave arrive come go
sit stand lie sleep wake rest run walk jump climb
buy sell spend save earn pay count measure
wear dress undress fold hang iron
lose find hide drop throw catch hold grab push pull
open close lock knock switch press
worry smile laugh cry shout whisper
mother father brother sister family friend
ceiling blackboard fan television bottle stone hill packet
towel classroom canteen assembly lantern treats
chopsticks stopwatches paintbrushes
nest den web burrow hive
tiger goat rabbit mice sheep cow bull
spelling dictation homework project group leader monitor prefect
curry ice sweet frozen fresh
toilet bathroom sink tap bucket
watermelon papaya guava mango peach
laundry washing line bucket
breakfast lunch dinner supper supper
fridge freezer store cupboard shelf
fork knife spoon plate bowl cup mug glass
uniform sportswear tracksuit
salt pepper sugar syrup
chalkboard textbook exercise notebook
scissors glue stapler
game games sport sports hobby club
candle lantern torch lamppost
aquarium pond stream river
roof gate fence wall path
hall corridor
belt pocket
chalk eraser
daycare
monkey donkey zebra giraffe lion tiger elephant leopard crocodile
dining hall bedroom
lesson lessons homework assignment
drums xylophone trumpet flute violin banjo
gardener baker butcher florist barber grocer jeweller
picnic reunion camping hiking
pillow blanket mattress
ferry yacht canoe kayak submarine
picnic meal snack
noise sound voice chatter whisper
luck fortune
bank letterbox postbox
oil fuel
salad soup dessert pie biscuit
thermos flask water bottle
thermos flask
newspaper magazine brochure
power electricity
mosque temple church
engineer mechanic driver
harbour dock runway
cereal toast sambal
music song
thunder lightning storm rainbow
thermometer
dot spot stripe stripey
rose orchid lily jasmine sunflower
pick collect gather
actor singer dancer
stick rope string wire
give lend borrow
neck tail wing paw hoof fur feather
plastic glass metal wood
fort castle palace
funicular cable car
bunga pandan
farmer writer painter singer
pangolin badger
motor engine wheel tyre
post stamp letter
dumpling ketupat mooncake popiah
hen chick rooster
yee
whiteboard mat
lampshade cushion
cloud clouds
aeroplane
raincoat umbrella cap
basket box tin
give gift
pyjamas pyjama
clean up
bangkok
hornbill pigeon sparrow mynah
tailor
school recess pack return unpack deliver queue tidy serve share
""".split())

# The DSKP word lists are *spelling* lists of multisyllabic words, not a
# complete vocabulary, so the everyday core a pupil already owns in Year 1 has
# to be stated somewhere.  These are the concrete nouns, verbs and adjectives
# of a KSSR Year 1/2 classroom story: they are common, they are never the
# target of a spelling box, and leaving them out made the gate reject honest
# sentences such as "The sun gives light to a flower."  Words still on the
# ladder for the year being tested come from :mod:`exam_gen.dskp_words`.
EVERYDAY = EVERYDAY | frozenset("""
sun sunshine ray heat warm cool chilly breeze
rain rainy drop puddle storm drizzle
flower blossom leaf leaves branch stem root seed grass bush hedge
tree trunk bark forest
ball balls bat glove racket goal net pitch
bench seat step steps stairs ladder railing gate
toy toys tool tools spoon fork
hand hands foot feet leg arm knee shoulder back
thing things someone someone anybody nobody everybody
live lives living lived love loves like liked likes lovely
story stories tale poem song rhyme
time times clock o'clock hour minute while during between
see saw seen look watched watching hear heard listen
wet dry warm cool dirty clean tidy
before after ago last next then today tomorrow yesterday
away back here near far close together apart
little tiny big huge great small
same different other another each every any all none both
call called calling shout shouted whisper whispered
throw threw catch caught kick kicked
win wins won score scores match matches team teams player
goal goals cup trophy coach captain
straw hay soil mud sand beach shore coast wave waves
shell shells crab crabs shell
carrot peas beans corn pumpkin
bun buns biscuit sandwich
snowman snowflake icicle
piano keyboard keys hour minute
basket tubs bucket bottles can cans jar
later soon already yet still
because so but although while until unless whether
read reads reading write writes writing draw draws drawing
sit sits sitting stand stands standing lie lies lying
walk walks walking run runs running talk talks talking
work works working worked
get gets getting put puts keep keeps
favourite favorite heavy kind cross strong blow blow blows blowing
fall falls fell road roads past pasts noon midday road
say says doing done having being made taken given given
teach taught seek sought fight fought write written grow grown
draw drawn choose chosen speak spoken steal stolen wear worn
freeze froze lose lost meet met pay paid ride ridden rise risen
shake shook shoot shot shut sleep slept spend spent swear swore
throw thrown understand understood wake woke win wins win won
keep kept leave left feel felt hold held hear heard hide hid
hurt hurt lend lent mean meant send sent build built burn burnt
ring rang sink sank speed spin spun stick stuck swing swung
tear torn weep wept dig dug
football rugby hockey badminton net nets
restaurant cafe food foods drink drinks meal meals
afraid birthday lake lakes month months photo photos photograph
village villages crow crows jug jugs bottle top bottom
animal animals visitor visitors best better half halves
practise practice hug present presents surprise surprised
fever headache high medicine medicines ill sick patient
room rooms wall walls floor ceiling lamp curtain sofa
basket bicycle boat ship bus train taxi car van plane
week weekend month year today tomorrow yesterday
busy early late tired ready careful safely slowly
problem problems idea ideas story stories picture pictures
mr mrs miss dr ms prof madam
ipoh penang johork bahru johor kedah kelantan perak
please right left turn turns science menu menus cost costs
dictionary dictionaries word words clever smart useful meaning
spell spelling meaning meanings
ringgit ringgit dollars use uses useful using
piece pieces slice slices corner corners
""".split())


def _dists() -> frozenset:
    return frozenset().union(FUNCTION, CLOSED, PROPER, EVERYDAY, LOCAL)


#: Extra vocabulary unlocked at a year and above.
#:
#: The DSKP word lists are *spelling* lists of multisyllabic words, so they say
#: nothing about the ordinary language a pupil meets in a reading text.  A Year
#: 5 story about a football tournament cannot avoid the word *tournament*, and
#: a Year 6 text on emergencies cannot avoid *emergency* — yet both are below
#: the child.  These tiers restore the missing middle of the ladder, keyed to
#: the RPT themes the year actually owns (Year 5: Towns and Cities, Days, Wild
#: Life, Learning World, Food and Health, Sport, Growing Up, Going Away;
#: Year 6: emergencies, the past, adventure, jobs, transport, how things are
#: made, music, telling stories, opinion, and mysteries).
#:
#: The tiers are cumulative and year-gated on purpose: *endangered* is a Year 6
#: DSKP word, so a Year 5 paper must still refuse it, and a Year 5 term word
#: such as *canteen* stays out of a Year 1 option.
EVERYDAY_BY_YEAR: dict[int, frozenset] = {
    5: frozenset("""
part parts promise promises promised think thinks thought whole wholly
learn learns learned learning know knows knew known remember remembers
health healthy illness hurt hurts pain painful sore throat cough cold flu
danger dangerous danger safety safe safely careful careless correct wrong
plenty enough quantity medicine medicines tablets pharmacist clinic
leaflet leaflets prescription dose warning warn warned warning ignore
ignored straight straightaway younger elder eldest older oldest age
town towns city cities street streets area areas thousand million
number numbers amount plenty pupil pupils student students classmates
classmate teacher teachers headmaster headmistress principal
term terms year years month months week weeks weekend session
subject subjects skill skills lesson lessons homework notebook
library librarian borrow borrows book books novel novels story stories
report reports title titles list lists challenge challenges
continue continues continued hope hopes plan plans
body bodies brain concentrate concentrates concentration energy
hurry hurries rushed explain explains explained explainer
happen happens happened nothing something everything anything
change changes changed changing routine routines
person persons somebody someone everybody everyone nobody nobody
alone lonely together apart except
price prices cost costs cheap cheaper expensive value pay
oats porridge protein vitamin energy carbohydrate balanced
breakfast lunch dinner supper meal meals snack canteen menu waiter
salad fruit vegetables egg eggs bread toast cereal
shop keeper owner driver rider player captain coach referee
match matches game games tournament trophy final finals
goalkeeper penalty penalties score scores point points
training train trains practise practice injured injury leg legs
competition race racing winner winning beat beaten lose lost
easy difficult hard soft hard difficult
smart clever quick quickly slow slowly strong stronger strong
weak weaker soft gentle safe safety
row rows line lines plant plants grow grows growing
seed seeds harvest harvested soil pot pot pots vegetable vegetables
sweet potato potatoes chilli chillies bean beans maize corn
patient patiently attentive attention group groups
responsibility responsible note notes notebook diaries diary
experiment experiments result results scientist scientists
nature natural patiently success successful
busiest busiest hurry early later nearest
journey journeys trip trips travel travels tourist tourists
overseas abroad luggage suitcase passports passport
airport station harbour ferry boat ships ship train bus
photo photograph video camera mobile phone laptop screen
council service services square twice front life lives easier
monsoon radio waste frightening hottest wettest wetter
orangutan orangutans ape apes sepilok rehabilitation rescued rescue
rescuer species species' carton countries country worker workers
became become heron herons biologist drain hunt hunts hunting
shallow large real need needs patience
awake cannot period simple simpler taking takes took
leftover even important learnt supporting support brave bravery
break breaks shy shyly front if whether
boring checked check dishes easily retired retirement seventy
wants want excited excitement forward full fully future money
university university whenever australia island islands turtle
turtles coconut fisherman fishermen hired rough through world
rare wild wildlife brave braver bravest
centre center middle sailor sailors
coming strokes stroke weekdays nervous strictly strict
""".split()),
    6: frozenset("""
emergency emergencies ambulance paramedic firefight firefighter
firefighters police officer officers accident collisions crash
evacuate evacuation shelter survivor survivors victim
danger dangerous emergency respond response rescue rescued
rescue centre shelter tent alarm siren
century centuries decade decades ancient ancient artefact artefacts
historic historical museum heritage tradition traditional ancient
kingdom empire village settlers settler ancestor ancestors
archaeology dig excavation excavation
adventure adventurer explore explorer exploration
explorer jungle island desert mountain climb climbing expedition
compass map maps route trails trail
job jobs career careers profession professional employee employer
worker workers workplace office studio laboratory laboratory
scientist scientists engineer engineering inventor invention
interview interviews qualify qualification skill skills
ambulance mechanic mechanic
transport transportation carriage carriage
traffic railway engine carriage platform passengers
manufacture factory factories produce produces producer
machine machines engine engines tool tools equipment equipment
material materials plastic metal wood glass paper
product products package packages bottle bottles
factory factory worker
music musical musician musicians band bands song songs
singer singers choir orchestra instrument instruments guitar violin
drum drums piano melody rhythm beat rhythm song lyrics
compose composer composed composition performance concert
opinion opinions believe believes agree disagree
argue argues argument explain explanation reason reasons
evidence prove proof mystery mysterious clue clues detective
solve solved solution puzzle riddles puzzle
witness witness witness statement suspect innocent guilty
silence silent secret secrets whisper whisper
gossip rumor rumour
flood floods flooded flooding drainage drain drains warning warned
afterwards district government headman loudspeaker neighbouring payment
reached refused usual community communities volunteer volunteers relief
supplies tent shelter belongings
power electricity line lines generator supply supplies technician
repair repaired repairer truck trucks soldier soldiers distributed
helpless clothes cupboard books lamps
wooden stilts wooden kilometre kilometres dawn dusk cockerels
exchanged exchange offered offer passing passed boat boats seller
capital capital state provincial
cave caves climbing climber climbers entrance entered expected
limestone rope ropes tied tie twisted ankle stretcher bandages
signalled calm risk risks operation member members within worth
rock rocks waterfall stream valley rope route trail tracks footprints
bandage wound wounds slipped slip slippery
vet veterinary advice disease farm farms farms injection injections
preventive single moment moments thanks grateful treating treatment
pet pets livestock poultry cattle
civil engineering drawing drawings designs site sites block blocks
laid ordinary redesigned damaged floodwater ground ground
steel iron frame frames tube tubes mill mills screw screws nut nuts
brakes brake handle handlebar seat saddle pedal chain gear
bend bent fits fit tested tightens tighten sold sells truck vans
flour dough yeast bacteria oven ovens oven rack racks simplest
mince yeast mix mixed mixing wrapped wrap cooling cool
kill killed baking baked flour sifted yeast
folk tune tunes melody melodies harmony rhythm beat beats clapped clap
arrangement arranged audience judge judging state contest complete
completely main fitting fit dislike dislikes else mind moment
bamboo bamboo grove mature matured poor richest satisfied sold
double north south east west region
son sons destroyed ruins
mystery mysterious clue clues clue detective solve solved solution
puzzle puzzles riddle riddles witness suspects innocent guilty
silence silent secret secrets gossip whisper rumours
stranger shed footprints thief thieves locked lock gate gates
police policeman policewoman officer officers
van vans old ancient historic historical museum heritage
tradition traditional century decade decades kingdom empire
settlers settler ancestors ancestor
dig digging excavation artifact artefact
journey journeys explore explorer exploring exploration
jungle desert mountain peak ridge slopes
compass maps chart route
job jobs career careers profession professional employee employer
workplace office studio laboratory
engineers inventor invention inventions
interview interviewed qualify qualification skills
transport transportation carriage railway platform passengers
manufacture manufacturer manufacturing factory factories produce
producer product products package packages bottle
material materials equipment tool
music musician musicians band bands song songs
composer composed composition performance concert
guitar piano drum violin flute trumpet harmonica
lyrics verse chorus tune
opinion opinions believe believes believe agree disagrees
argument argue explanation reason evidence prove proof
tried trying decide decided decision opinion
deserve fair unfair
clear cleared neighbor neighbour neighbours clearing
himself herself itself themselves myself ourselves yourself
adult adults follow follows followed following guide guides guided
fire fires lit light lights
way ways free freely saving save saves
course courses itself making make makes made test tested tests
mine mines begin began begun start starts started
able cause causes caused habit habits
connected connect copies copy copy mark marks marked
necessary necessary question questions rule rules ruled
survey surveys useful useless
warehouse warehouses extinguisher flame flames smoke smelled smells
chemical chemicals shopkeeper caretaker key keys specimen specimens
ashamed punish punished punishment sure belonging belonged belongs
hidden hide hid point points direction directions route
passenger pedestrians platform crossings junction
order ordered towards toward
appointment appointments conductor operator reaches reach terminal
bell cycling cycle drive drives repeat simply
""".split()),
}


def _tiers(year: int | None) -> frozenset:
    """The extra vocabulary unlocked for ``year`` and every year above it."""
    if year is None:
        return frozenset().union(*EVERYDAY_BY_YEAR.values()) if \
            EVERYDAY_BY_YEAR else frozenset()
    out: set = set()
    for start, words in EVERYDAY_BY_YEAR.items():
        if year >= start:
            out |= words
    return frozenset(out)


#: Year-neutral pool only.  The tiered words are deliberately *not* merged in
#: here: a flat pool would let a Year 1 option use "tournament", which is the
#: whole point of gating them by year.  Callers that need options for a year
#: must go through :func:`allowed`, which applies the tier.
DISTRACTOR_OK = _dists()


def allowed(word: str, year: int | None = None) -> bool:
    """True when ``word`` is fit to appear in a paper for ``year``.

    Officiallisted for the year (or below) is always fine.  Otherwise a word
    is acceptable only if it is a closed-set item — a function word, a number,
    a day, or familiar everyday vocabulary.  ``year`` may be ``None`` to
    ignore the ladder (used where the target word is deliberately rich, e.g.
    the Part 5 spelling boxes in Years 5-6).
    """
    w = normalise(word)
    if not w or not _WORD.match(w):
        return False
    if year is not None and in_list(w, year):
        return True
    if any(s in DISTRACTOR_OK for s in _stems(w)):
        return True
    tier = _tiers(year)
    if tier and tier is not None:
        return any(s in tier for s in _stems(w))
    return False


def off_curriculum(words, year: int) -> list[str]:
    """Every word in ``words`` that a pupil of ``year`` should not be asked.

    Accepts a list of words or of MCQ option dicts, and returns the offending
    words sorted and de-duplicated so a report is stable between runs.
    """
    if isinstance(words, str):
        words = [words]
    out: set = set()
    for item in words or []:
        if isinstance(item, dict):
            for key in ("word", "answer", "ans_text", "target", "clue"):
                if item.get(key):
                    out.add(str(item[key]))
            opts = item.get("opts")
            if isinstance(opts, (list, tuple)):
                for o in opts:
                    if isinstance(o, str):
                        out.add(o)
        elif isinstance(item, str):
            out.add(item)
    bad = set()
    for raw in out:
        w = normalise(raw)
        if w and _WORD.match(w) and not allowed(w, year):
            bad.add(w)
    return sorted(bad)


# ---------------------------------------------------------------------------
# Round 30 (F6): DSKP coverage report per paper
# ---------------------------------------------------------------------------
#: The six part kinds a paper can actually contain, mapped to the DSKP standard
#: codes each one exercises (see ``data.JSU_STANDARDS`` for the wording).
_KIND_STANDARDS = {
    "vocab":         ("3.2.2",),
    "cloze":         ("3.2.3",),
    "comprehension": ("3.2.2", "3.3.1"),
    "match":         ("3.2.2",),
    "words":         ("3.2.3",),
    "writing":       ("4.2.1", "4.2.2"),
}


def _part_standards(part, year: int) -> list[str]:
    """Standards a part exercises, from its kind."""
    kind = str(getattr(part, "kind", "") or "")
    codes = _KIND_STANDARDS.get(kind)
    if codes is None:
        # unknown kind: fall back to the reading-understanding standard rather
        # than inventing a mapping
        codes = ("3.2.2",)
    return list(codes)

def coverage_report(paper) -> dict:
    """Return a dict representing DSKP coverage for the given paper.

    ``text`` is a printable, principal-facing audit block: the standards
    covered and a per-part breakdown with question ranges and marks.
    """
    from collections import Counter
    from . import data as D
    try:
        year = int(paper.year())
    except Exception:
        year = int(getattr(paper, "meta", {}).get("year", 1) or 1)

    parts_rep = []
    all_codes: Counter = Counter()
    for p in getattr(paper, "parts", []):
        codes = _part_standards(p, year)
        for c in codes:
            all_codes[c] += 1
        qfirst = int(getattr(p, "qfirst", 0) or 0)
        qcount = len(getattr(p, "items", []))
        parts_rep.append({
            "name": getattr(p, "name", "") or getattr(p, "kind", ""),
            "kind": getattr(p, "kind", ""),
            "first": qfirst,
            "last": (qfirst + qcount - 1) if qcount else qfirst,
            "items": qcount,
            "marks": getattr(p, "marks", 0),
            "standards": codes,
        })

    codes_list = sorted(all_codes.keys())
    lines = [f"DSKP coverage - Year {year}", "=" * 36]
    lines.append(f"Standards covered ({len(codes_list)}): " +
                 (", ".join(codes_list) if codes_list else "(none)"))
    lines.append("")
    for pr in parts_rep:
        span = (f"{pr['first']}-{pr['last']}" if pr["items"] > 1
                else str(pr["first"]))
        lines.append(f"  Part {span}  [{pr['marks']}m / {pr['items']} items]  "
                     f"{pr['kind']}  ->  {', '.join(pr['standards'])}")
    lines.append("-" * 36)
    for c in codes_list:
        desc = D.JSU_STANDARDS.get(c, {}).get(year)
        if desc:
            lines.append(f"  {c}: {desc}")
    lines.append("=" * 36)
    return {
        "year": year,
        "standards": codes_list,
        "parts": parts_rep,
        "coverage": dict(all_codes),
        "text": "\n".join(lines),
    }
