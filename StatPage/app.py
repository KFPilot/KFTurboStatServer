from flask import Flask, render_template, abort, request
import db

app = Flask(__name__)
app.jinja_env.filters["gametype_name"] = db.gametype_display_name
app.jinja_env.filters["card_name"] = db.card_display_name
app.jinja_env.filters["difficulty_name"] = db.difficulty_display_name

@app.context_processor
def inject_filter_context():
    all_gametypes = db.get_gametypes()
    all_difficulties = db.get_difficulties()

    selected_gt = [g for g in request.args.getlist("gametypes") if g in all_gametypes]
    if "gametypes" not in request.args:
        selected_gt = list(all_gametypes)

    selected_diff = []
    for d in request.args.getlist("difficulties"):
        try:
            v = int(d)
            if v in all_difficulties:
                selected_diff.append(v)
        except ValueError:
            pass
    if "difficulties" not in request.args:
        selected_diff = list(all_difficulties)

    parts = [f"gametypes={g}" for g in selected_gt] if selected_gt else ["gametypes="]
    parts += [f"difficulties={d}" for d in selected_diff] if selected_diff else ["difficulties="]
    return {
        "all_gametypes": all_gametypes,
        "selected_gametypes": selected_gt,
        "all_difficulties": all_difficulties,
        "selected_difficulties": selected_diff,
        "filter_qs": "&".join(parts),
    }

def _get_gametypes_filter():
    all_gametypes = db.get_gametypes()
    if "gametypes" not in request.args:
        return None
    selected = [g for g in request.args.getlist("gametypes") if g in all_gametypes]
    return selected if selected else []

def _get_difficulties_filter():
    all_difficulties = db.get_difficulties()
    if "difficulties" not in request.args:
        return None
    selected = []
    for d in request.args.getlist("difficulties"):
        try:
            v = int(d)
            if v in all_difficulties:
                selected.append(v)
        except ValueError:
            pass
    return selected if selected else []

@app.route("/")
def index():
    overview = db.get_aggregate_overview(_get_gametypes_filter(), _get_difficulties_filter())
    return render_template("index.html", overview=overview)

@app.route("/leaderboards")
def leaderboards():
    players = db.get_all_player_stats(_get_gametypes_filter(), _get_difficulties_filter())
    return render_template("leaderboards.html", players=players)

@app.route("/player/<playertableid>")
def player_detail(playertableid):
    if not playertableid.startswith("player_") or not playertableid[7:].isalpha():
        abort(404)
    data = db.get_player_detail(playertableid, _get_gametypes_filter(), _get_difficulties_filter())
    if not data:
        abort(404)
    return render_template("player.html", data=data)

@app.route("/cards")
def cards():
    card_stats = db.get_card_stats()
    return render_template("cards.html", cards=card_stats, card_names=db.CARD_NAMES)

@app.route("/perks")
def perks():
    perk_stats = db.get_perk_stats(_get_gametypes_filter(), _get_difficulties_filter())
    return render_template("perks.html", perks=perk_stats)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
