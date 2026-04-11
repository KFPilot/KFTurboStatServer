from flask import Flask, render_template, abort, request
import db

app = Flask(__name__)
app.jinja_env.filters["gametype_name"] = db.gametype_display_name
app.jinja_env.filters["card_name"] = db.card_display_name

@app.context_processor
def inject_filter_context():
    all_gametypes = db.get_gametypes()
    selected = request.args.getlist("gametypes")
    # Validate: only allow known gametypes
    selected = [g for g in selected if g in all_gametypes]
    gametypes = selected if selected else None
    return {
        "all_gametypes": all_gametypes,
        "selected_gametypes": selected,
        "filter_qs": "&".join(f"gametypes={g}" for g in selected) if selected else "",
    }

def _get_gametypes_filter():
    all_gametypes = db.get_gametypes()
    selected = request.args.getlist("gametypes")
    selected = [g for g in selected if g in all_gametypes]
    return selected if selected else None

@app.route("/")
def index():
    overview = db.get_aggregate_overview(_get_gametypes_filter())
    return render_template("index.html", overview=overview)

@app.route("/leaderboards")
def leaderboards():
    players = db.get_all_player_stats(_get_gametypes_filter())
    return render_template("leaderboards.html", players=players)

@app.route("/player/<playertableid>")
def player_detail(playertableid):
    if not playertableid.startswith("player_") or not playertableid[7:].isalpha():
        abort(404)
    data = db.get_player_detail(playertableid, _get_gametypes_filter())
    if not data:
        abort(404)
    return render_template("player.html", data=data)

@app.route("/cards")
def cards():
    card_stats = db.get_card_stats()
    return render_template("cards.html", cards=card_stats, card_names=db.CARD_NAMES)

@app.route("/perks")
def perks():
    perk_stats = db.get_perk_stats(_get_gametypes_filter())
    return render_template("perks.html", perks=perk_stats)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
