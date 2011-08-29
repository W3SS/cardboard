import mock

from cardboard import core as c, exceptions, phases
from cardboard.events import events
from cardboard.tests.util import GameTestCase


class TestManaPool(GameTestCase):
    def test_iter(self):
        self.p1.mana_pool += (1, 2, 3, 4, 5, 6)
        self.assertEqual(list(self.p1.mana_pool), [1, 2, 3, 4, 5, 6])

    def test_iadd_isub(self):
        self.p1.mana_pool += (2, 4, 6, 8, 10, 12)
        self.p1.mana_pool += (2, 4, 6, 8, 10, 12)

        self.assertEqual(self.p1.mana_pool.white, 4)
        self.assertEqual(self.p1.mana_pool.blue, 8)
        self.assertEqual(self.p1.mana_pool.black, 12)
        self.assertEqual(self.p1.mana_pool.red, 16)
        self.assertEqual(self.p1.mana_pool.green, 20)
        self.assertEqual(self.p1.mana_pool.colorless, 24)

        self.p1.mana_pool -= (2, 4, 6, 8, 10, 12)
        self.assertEqual(self.p1.mana_pool.contents, (2, 4, 6, 8, 10, 12))

        self.p1.mana_pool -= (2, 4, 6, 8, 10, 12)
        self.assertTrue(self.p1.mana_pool.is_empty)

        self.assertIs(NotImplemented, self.p1.mana_pool.__iadd__(object()))
        self.assertIs(NotImplemented, self.p1.mana_pool.__isub__(object()))

        # non-length 6 sequence should be a ValueError
        with self.assertRaises(ValueError):
            self.p1.mana_pool += (1, 2, 3)

        with self.assertRaises(ValueError):
            self.p1.mana_pool -= (1, 2, 3)

    def test_repr(self):
        self.assertEqual(repr(self.p1.mana_pool), "(0W, 0U, 0B, 0R, 0G, 0)")

        for i, color in enumerate(self.p1.mana_pool.COLORS):
            setattr(self.p1.mana_pool, color, i)

        self.assertEqual(repr(self.p1.mana_pool), "(0W, 1U, 2B, 3R, 4G, 5)")

    def test_colors(self):
        self.assertEqual(self.p1.mana_pool.COLORS, ("white", "blue",
                         "black", "red", "green", "colorless"))

    def test_mana_changed(self):
        mana_events = events["player"]["mana"]

        for color in self.p1.mana_pool.COLORS:
            current = getattr(self.p1.mana_pool, color)
            setattr(self.p1.mana_pool, color, current)
            self.assertLastEventsWereNot([mana_events[color]["added"]])

            setattr(self.p1.mana_pool, color, 100)
            self.assertLastEventsWere([mana_events[color]["added"]])

            setattr(self.p1.mana_pool, color, 10)
            self.assertLastEventsWere([mana_events[color]["removed"]])

    def test_is_empty(self):
        self.assertTrue(self.p1.mana_pool.is_empty)
        self.p1.mana_pool += (1, 2, 3, 4, 5, 6)
        self.assertFalse(self.p1.mana_pool.is_empty)

    def test_empty(self):
        self.p1.mana_pool += (1, 2, 3, 4, 5, 6)
        self.p1.mana_pool.empty()
        self.assertTrue(self.p1.mana_pool.is_empty)


class TestPlayer(GameTestCase):
    def test_repr_str(self):
        p3 = self.game.add_player(library=[], name="Test")
        self.assertEqual(repr(p3), "<Player: Test>")

        p4 = self.game.add_player(library=[])
        self.assertEqual(repr(p4), "<Player>")

    def test_sets_card_attribs(self):
        for card in self.p1.library:
            self.assertIs(card.game, self.p1.game)
            self.assertIs(card.owner, self.p1)
            self.assertIs(card.controller, self.p1)

        for card in self.p2.library:
            self.assertIs(card.game, self.p2.game)
            self.assertIs(card.owner, self.p2)
            self.assertIs(card.controller, self.p2)

    def test_life(self):
        self.game.start()

        self.p1.life += 2
        self.assertLastEventsWere([events["player"]["life"]["gained"]])
        self.assertEqual(self.p1.life, 22)

        self.p1.life -= 2
        self.assertLastEventsWere([events["player"]["life"]["lost"]])
        self.assertEqual(self.p1.life, 20)

    def test_life_not_changed(self):
        self.game.start()
        self.p1.life += 0
        self.assertLastEventsWereNot([events["player"]["life"]["gained"]])
        self.assertLastEventsWereNot([events["player"]["life"]["lost"]])

    def test_concede(self):
        self.game.start()

        self.assertFalse(self.p1.dead)
        self.p1.concede()

        self.assertEqual(self.p1.death_by, "concede")
        self.assertTrue(self.p1.dead)

        self.assertLastEventsWere([events["player"]["conceded"],
                                   events["player"]["died"]])

    def test_die(self):
        self.game.start()
        self.assertFalse(self.p1.dead)
        self.p1.die("test")

        self.assertTrue(self.p1.dead)
        self.assertEqual(self.p1.death_by, "test")

        self.assertLastEventsWere([events["player"]["died"]])

        # can't die twice
        self.resetEvents()
        self.assertRaises(exceptions.InvalidAction, self.p1.die, "test2")
        self.assertLastEventsWereNot([events["player"]["died"]])

    def test_draw(self):
        self.game.start()
        top = self.p1.library[-1]

        self.assertIn(top, self.p1.library)
        self.assertNotIn(top, self.p1.hand)

        self.p1.draw()

        self.assertIn(top, self.p1.hand)
        self.assertNotIn(top, self.p1.library)

        self.assertLastEventsWere([events["player"]["draw"]])

        self.resetEvents()

        top = self.p2.library[-5:]
        self.p2.draw(5)

        for card in top:
            self.assertIn(card, self.p2.hand)

        self.assertTriggered([{"event" : events["player"]["draw"]}] * 5)

    def test_draw_zero(self):
        self.game.start()

        self.p1.draw(53)
        self.assertFalse(self.p1.library)
        self.assertFalse(self.p1.dead)

        self.p1.draw(0)
        self.assertFalse(self.p1.library)
        self.assertFalse(self.p1.dead)
        self.assertFalse(self.p1._drew_from_empty_library)

    def test_draw_empty_library(self):
        self.game.start()

        self.p1.draw(100)

        self.assertEqual(len(self.p1.hand), 60)
        self.assertFalse(self.p1.library)
        self.assertTrue(self.p1._drew_from_empty_library)

    def test_negatives(self):
        self.assertRaises(ValueError, self.p1.draw, -1)

        for color in self.p1.mana_pool.COLORS:
            with self.assertRaises(ValueError):
                setattr(self.p1.mana_pool, color, -1)

    def test_shallow_copies_library(self):
        library = [mock.Mock() for _ in range(10)]
        p3 = self.game.add_player(library=library)

        self.assertIsNot(p3.library, library)
        self.assertEqual(list(p3.library), library)

        for card, original in zip(p3.library, library):
            self.assertIs(card, original)


class TestGame(GameTestCase):
    def test_no_player_game(self):
        game = c.Game(self.events)
        self.assertRaises(exceptions.InvalidAction, game.start)

    def test_start(self):
        self.game.start()
        event = {"event" : events["game"]["started"]}
        self.assertEqual(self.events.trigger.call_args_list[0], [event])

    def test_shuffles(self):
        """
        The game start shuffles the players' libraries.

        .. seealso::
            :ref:`shuffle`

        """

        self.p1.library.shuffle = mock.Mock()
        self.p2.library.shuffle = mock.Mock()

        self.game.start()
        self.p1.library.shuffle.assert_called_once_with()
        self.p2.library.shuffle.assert_called_once_with()

    def test_init_life_and_draw(self):
        """
        The game start sets the life total and draws cards.

        .. seealso::
            :ref:`life-and-draw`

        """

        with mock.patch.object(self.p1, "draw") as draw_p1:
            with mock.patch.object(self.p2, "draw") as draw_p2:
                self.game.start()

        draw_p1.assert_called_once_with(7)
        draw_p2.assert_called_once_with(7)

        self.assertEqual(self.p1.life, 20)
        self.assertEqual(self.p2.life, 20)

    def test_add_player_started(self):
        self.game.start()

        with self.assertRaises(exceptions.InvalidAction):
            self.game.add_player(library=self.library)

        with self.assertRaises(exceptions.InvalidAction):
            player = c.Player(game=self.game, library=self.library)
            self.game.add_existing_player(player)

        self.assertNotIn(player, self.game.players)

    def test_end(self):
        self.game.start()
        self.assertFalse(self.game.ended)

        self.game.end()
        self.assertLastEventsWere([events["game"]["ended"]])
        self.assertTrue(self.game.ended)

    def test_end_if_dead(self):
        """
        The game ends when there is one person left.

        .. seealso::
            :ref:`last-man-standing`

        """

        self.game.add_existing_player(self.p3)
        self.game.start()

        self.assertFalse(self.game.ended)

        self.p1.die("test")
        self.game.end_if_dead()
        self.assertFalse(self.game.ended)

        self.p2.die("test")
        self.game.end_if_dead()
        self.assertTrue(self.game.ended)

        self.assertFalse(self.p3.dead)

    def test_frontends(self):
        self.p1.frontend = object()
        self.p2.frontend = object()

        self.assertEqual(self.game.frontends, {self.p1 : self.p1.frontend,
                                               self.p2 : self.p2.frontend})


class TestStateBasedEffects(GameTestCase):
    def test_no_life(self):
        """
        A player with 0 or less life loses.

        .. seealso::
            :ref:`no-life`

        """

        self.p1.life -= 20
        self.game._check_state_based_actions()
        self.assertTrue(self.p1.dead)
        self.assertEqual(self.p1.death_by, "life")

    def test_draw(self):
        """
        A player that drew from an empty library dies.

        .. seealso::
            :ref:`no-library`

        """

        self.p1.draw(100)
        self.game._check_state_based_actions()
        self.assertTrue(self.p1.dead)
        self.assertEqual(self.p1.death_by, "library")

    def test_poison(self):
        """
        A player with 10 or more poison counters is dead.

        .. seealso::
            :ref:`too-much-poison`

        """

        self.p1.poison = 10
        self.game._check_state_based_actions()
        self.assertTrue(self.p1.dead)
        self.assertEqual(self.p1.death_by, "poison")


class TestTurnManager(GameTestCase):
    def test_initialize_turn_and_phase(self):
        self.game.start()
        self.assertIn(self.game.turn.active_player, {self.p1, self.p2})
        self.assertEqual(self.game.turn.phase, phases.beginning)
        self.assertEqual(self.game.turn.step, phases.beginning[0])

    def do_tst_end(self):
        self.resetEvents()

        active = self.game.turn.active_player
        other = next(p for p in self.game.players if p != active)

        self.game.turn.end()

        self.assertIs(self.game.turn.active_player, other)
        self.assertTriggered([{"event" : events["game"]["turn"]["ended"]},
                              {"event" : events["game"]["turn"]["started"]}])

    def test_end(self):
        self.game.start()
        self.do_tst_end()

        # move to the middle of a turn somewhere to check it works from there
        for i in range(4):
            self.game.turn.next()

        self.do_tst_end()

    def test_next(self):

        pe = events["game"]["turn"]["phase"]

        self.game.start()

        for _ in range(2):

            self.game.turn.end = mock.Mock()

            self.assertEqual(self.game.turn.phase, phases.beginning)
            self.assertEqual(self.game.turn.step, phases.untap)

            self.assertTriggered([
                {"event" : pe["beginning"]["started"]},
                {"event" : pe["beginning"]["untap"]["started"]},
            ])

            self.game.turn.next()

            self.assertEqual(self.game.turn.phase, phases.beginning)
            self.assertEqual(self.game.turn.step, phases.upkeep)

            self.assertTriggered([
                {"event" : pe["beginning"]["untap"]["ended"]},
                {"event" : pe["beginning"]["upkeep"]["started"]},
            ])

            self.game.turn.next()

            self.assertEqual(self.game.turn.phase, phases.beginning)
            self.assertEqual(self.game.turn.step, phases.draw)

            self.assertTriggered([
                {"event" : pe["beginning"]["upkeep"]["ended"]},
                {"event" : pe["beginning"]["draw"]["started"]},
            ])

            self.game.turn.next()

            self.assertEqual(self.game.turn.phase, phases.first_main)
            # TODO: self.assertEqual(self.game.turn.step, None)

            self.assertTriggered([
                {"event" : pe["beginning"]["draw"]["ended"]},
                {"event" : pe["beginning"]["ended"]},
                {"event" : pe["first_main"]["started"]},
            ])

            self.game.turn.next()

            self.assertEqual(self.game.turn.phase, phases.combat)
            self.assertEqual(self.game.turn.step, phases.beginning_of_combat)

            self.assertTriggered([
                {"event" : pe["first_main"]["ended"]},
                {"event" : pe["combat"]["started"]},
                {"event" : pe["combat"]["beginning"]["started"]},
            ])

            self.game.turn.next()

            self.assertEqual(self.game.turn.phase, phases.combat)
            self.assertEqual(self.game.turn.step, phases.declare_attackers)

            self.assertTriggered([
                {"event" : pe["combat"]["beginning"]["ended"]},
                {"event" : pe["combat"]["declare_attackers"]["started"]},
            ])

            self.game.turn.next()

            self.assertEqual(self.game.turn.phase, phases.combat)
            self.assertEqual(self.game.turn.step, phases.declare_blockers)

            self.assertTriggered([
                {"event" : pe["combat"]["declare_attackers"]["ended"]},
                {"event" : pe["combat"]["declare_blockers"]["started"]},
            ])

            self.game.turn.next()

            self.assertEqual(self.game.turn.phase, phases.combat)
            self.assertEqual(self.game.turn.step, phases.combat_damage)

            self.assertTriggered([
                {"event" : pe["combat"]["declare_blockers"]["ended"]},
                {"event" : pe["combat"]["combat_damage"]["started"]},
            ])

            self.game.turn.next()

            self.assertEqual(self.game.turn.phase, phases.combat)
            self.assertEqual(self.game.turn.step, phases.end_of_combat)

            self.assertTriggered([
                {"event" : pe["combat"]["combat_damage"]["ended"]},
                {"event" : pe["combat"]["end"]["started"]},
            ])

            self.game.turn.next()

            self.assertEqual(self.game.turn.phase, phases.second_main)
            # TODO: self.assertEqual(self.game.turn.step, None)

            self.assertTriggered([
                {"event" : pe["combat"]["end"]["ended"]},
                {"event" : pe["combat"]["ended"]},
                {"event" : pe["second_main"]["started"]},
            ])

            self.game.turn.next()

            self.assertEqual(self.game.turn.phase, phases.ending)
            self.assertEqual(self.game.turn.step, phases.end)

            self.assertTriggered([
                {"event" : pe["second_main"]["ended"]},
                {"event" : pe["ending"]["started"]},
                {"event" : pe["ending"]["end"]["started"]},
            ])

            self.game.turn.next()

            self.assertEqual(self.game.turn.phase, phases.ending)
            self.assertEqual(self.game.turn.step, phases.cleanup)

            self.assertTriggered([
                {"event" : pe["ending"]["end"]["ended"]},
                {"event" : pe["ending"]["cleanup"]["started"]},
            ])

            self.assertFalse(self.game.turn.end.called)
            self.game.turn.next()
            self.assertTrue(self.game.turn.end.called)

            self.assertTriggered([
                {"event" : pe["ending"]["cleanup"]["ended"]},
                {"event" : pe["ending"]["ended"]},
            ])

    def test_empties_mana_pool_on_each_step(self):
        """
        The mana pool should empty at the end of each phase or step.

        """

        self.game.start()

        for _ in range(20):
            self.p1.mana_pool += (1, 2, 3, 4, 5, 6)
            self.p2.mana_pool += (2, 2, 2, 2, 2, 2)

            self.game.turn.next()

            self.assertTrue(self.p1.mana_pool.is_empty)
            self.assertTrue(self.p2.mana_pool.is_empty)

    def test_unstarted_game(self):
        self.assertIs(self.game.ended, None)

        self.assertIs(self.game.turn.active_player, None)
        self.assertIs(self.game.turn.phase, None)
        self.assertIs(self.game.turn.step, None)

        self.assertFalse(self.game.started)

    def test_advance_unstarted_game(self):
        self.assertRaises(exceptions.InvalidAction, self.game.turn.next)
        self.assertRaises(exceptions.InvalidAction, self.game.turn.end)
