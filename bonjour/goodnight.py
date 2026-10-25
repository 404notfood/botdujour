"""Petites excuses absurdes pour le message automatique de fin de soirée."""
import secrets


REPLIES = (
    "Bon bah, c'est pas l'tout, mais j'ai aquaponey sur la Lune. Le poney a déjà mis son scaphandre. Bonne nuit les humains ! 🐴🌕",
    "Bon bah, c'est pas l'tout, mais j'ai curling sur Saturne. Avec tous ces anneaux, impossible de retrouver le parking. Bonne nuit ! 🥌🪐",
    "Je vous laisse, j'ai cours de claquettes avec un poulpe. Huit chaussures à lacer, on n'est pas couchés. Bonne nuit tout le monde ! 🐙👞",
    "Bon bah, c'est pas l'tout, mais je dois border mon grille-pain. Sans son histoire de biscotte, il fait des étincelles. Bonne nuit ! 🍞🛌",
    "Je file, j'ai une raclette avec les Martiens. Ils ont apporté les patates, mais personne n'a pensé à la gravité. Dormez bien ! 🧀👽",
    "Bon bah, c'est pas l'tout, mais mon dragon réclame sa promenade. La dernière fois, il a encore fait fondre la laisse. Bonne nuit ! 🐉🌙",
    "Je vous laisse, j'ai une réunion secrète avec les chaussettes disparues. Elles préparent leur retour dans un autre tambour. Bonne nuit ! 🧦🕵️",
    "Bon bah, c'est pas l'tout, mais j'ai yoga sur un astéroïde. La position du caillou, je maîtrise déjà. Bonne nuit les humains ! 🧘☄️",
    "Je file, mon nuage de compagnie refuse de dormir sans sa veilleuse. Il menace de faire un orage dans la cuisine. Bonne nuit ! ☁️💤",
    "Bon bah, c'est pas l'tout, mais j'ai karaoké avec les pingouins. Ils m'attendent pour Libérée, Dégivrée. Bonne nuit tout le monde ! 🐧🎤",
)


def make_goodnight() -> str:
    return secrets.choice(REPLIES)
