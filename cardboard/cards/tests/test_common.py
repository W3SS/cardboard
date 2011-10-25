import mock

from cardboard.tests.util import GameTestCase
from cardboard.cards import common as c
from cardboard.frontend.testing import TestingFrontend


class TestCommon(GameTestCase):
    def setUp(self):
        super(TestCommon, self).setUp()
        self.p1.frontend = TestingFrontend(self.p1)
        self.game.start()

    def test_draw_discard(self):
        draw = self.p1.library[-3:]
        discard = list(self.p1.hand)[:2]

        with self.p1.frontend.select.cards.will_return(*discard):
            c.draw_discard(self.p1, len(draw), len(discard), self.p1.exile)

        for card in draw:
            self.assertIn(card, self.p1.hand)

        for card in discard:
            self.assertIn(card, self.p1.exile)

        # default to is graveyard
        draw = self.p1.library[-1]
        discard = next(iter(self.p1.hand))

        with self.p1.frontend.select.cards.will_return(discard):
            c.draw_discard(self.p1, 1, 1)

        self.assertIn(discard, self.p1.graveyard)
