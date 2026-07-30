try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

from database import get_db


def get_curriculum_order(topic=None):
    db = get_db()
    all_topics = db.execute(
        "SELECT DISTINCT topic FROM quizzes ORDER BY topic"
    ).fetchall()
    db.close()

    topics = [t["topic"] for t in all_topics if t["topic"]]
    if not topics:
        return {"success": False, "message": "No topics available."}

    if NETWORKX_AVAILABLE:
        G = nx.DiGraph()
        for t in topics:
            G.add_node(t)
        for i, t in enumerate(topics):
            if i > 0:
                G.add_edge(topics[i - 1], t)
        if topic and topic in G:
            prereqs = list(nx.ancestors(G, topic))
            order = prereqs + [topic]
            return {"success": True, "topic": topic, "recommended_order": order}
        return {"success": True, "topology": list(G.nodes()), "message": "Topics linked in sequential order."}
    else:
        idx = topics.index(topic) if topic in topics else -1
        if topic and idx >= 0:
            return {"success": True, "topic": topic, "recommended_order": topics[:idx + 1]}
        return {"success": True, "topics": topics, "message": "Learn topics in this order for best progression."}
