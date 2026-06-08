from nodes import NODE_CLASS_MAPPINGS


def test_sample_node_runs():
    node = NODE_CLASS_MAPPINGS["SimpleMathNode"]()
    assert node.run(2, 3) == (5,)
