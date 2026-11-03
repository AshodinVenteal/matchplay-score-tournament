from flask import Flask, render_template
from .ranking import best_cards

app = Flask(__name__)
TITLE = "Score High for Trans Lives"
N_EXPANDED_CARDS = 3


@app.template_filter("commafy")
def commafy(value: int) -> str:
    "Apply thousands separator to integers"
    return "{:,d}".format(value)


@app.route("/ranking/<tournament_id>")
def render_ranking(tournament_id: int):
    cards = best_cards(tournament_id, use_cache=True)
    return render_template(
        "ranking.html", cards=cards, title=TITLE, n_expanded=N_EXPANDED_CARDS
    )
