from flask import Flask, render_template
from .ranking import best_cards

app = Flask(__name__)
N_EXPANDED_CARDS = 3
TOURNAMENT_INFO = {281672: "Test Tournament"}


@app.template_filter("commafy")
def commafy(value: int) -> str:
    "Apply thousands separator to integers"
    return "{:,d}".format(value)


@app.route("/ranking/<int:tournament_id>")
def render_ranking(tournament_id: int):
    cards = best_cards(tournament_id, use_cache=True)
    title = TOURNAMENT_INFO.get(tournament_id, "unknown tournament")
    return render_template(
        "ranking.html", cards=cards, title=title, n_expanded=N_EXPANDED_CARDS
    )


@app.route("/")
def index():
    return render_template("index.html", tournaments=TOURNAMENT_INFO)
