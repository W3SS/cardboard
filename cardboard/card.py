"""
This module implements the Magic: The Gathering game :term:`objects`.

"""

from cardboard import events, exceptions, types
from cardboard.ability import AbilityNotImplemented
from cardboard.cards import cards
from cardboard.db import models, Session
from cardboard.util import requirements


__all__ = ["Card", "Spell", "Token", "characteristics"]


def status(name, on_event, off_event, default=True):
    """
    Create a status attribute with togglers.

    """

    stupid_nonlocal = [default]

    @property
    def get(self):
        return stupid_nonlocal[0]

    def toggle(turn_on):
        if turn_on:
            event = on_event
        else:
            event = off_event

        def setter(self):
            self.game.require(started=True)
            self.require(zone=self.game.battlefield, **{name : not turn_on})

            stupid_nonlocal[0] = turn_on

            self.game.events.trigger(
                event=events.STATUS_CHANGED, card=self, status=event
            )

        return setter

    return get, toggle(turn_on=True), toggle(turn_on=False)


_tap = status("is_tapped", "tapped", "untapped", default=False)
_flip = status("is_flipped", "flipped", "unflipped", default=False)
_turn = status("is_face_up", "face up", "face down", True)
_phase = status("is_phased_in", "phased in", "phased out", default=True)


class Card(object):

    is_tapped, tap, untap = _tap
    is_flipped, flip, unflip = _flip
    is_face_up, turn_face_up, turn_face_down = _turn
    is_phased_in, phase_in, phase_out = _phase
    # XXX : only allow phasing / flipping / turning for stuff with those abils

    require = requirements(
        {"zone" : {"default" : "{self} was expected to be in a {expected.name}"
                               " zone, not '{got}'."}},
    )

    def __init__(self, db_card, _cards=cards):
        super(Card, self).__init__()

        self.game = None
        self.owner = None

        self.controller = None
        self._zone = None

        for attr in {"name", "loyalty", "mana_cost",
                     "types", "subtypes", "supertypes"}:
            setattr(self, attr, getattr(db_card, attr))

        if self.name in _cards:
            self.abilities = _cards[self.name](self, db_card.abilities)
        else:
            self.abilities = [AbilityNotImplemented] * len(db_card.abilities)

        self.power = self.base_power = db_card.power
        self.toughness = self.base_toughness = db_card.toughness

        self.can_attack = True
        self.damage = 0
        self._changed_colors = set()

    def __lt__(self, other):
        """
        Sort two cards alphabetically.

        """

        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.name < other.name

    def __str__(self):
        return str(self.name)

    def __unicode__(self):
        return unicode(self.name)

    def __repr__(self):
        return "<Card: {}>".format(self)

    @classmethod
    def load(cls, name, session=None):
        if session is None:
            session = Session()

        db_card = session.query(models.Card).filter_by(name=name).one()
        return cls(db_card)

    @property
    def colors(self):
        return (self._changed_colors or
                {i for i in self.mana_cost or "" if i.isalpha()})

    @property
    def zone(self):
        if self.game is None or not self.game.started:
            return

        if self._zone is None or self not in self._zone:
            for zone in (self.controller.exile, self.controller.hand,
                         self.game.battlefield, self.game.stack,
                         self.controller.graveyard, self.controller.library):

                if self in zone:
                    self._zone = zone

        return self._zone

    def play(self):
        """
        Play the card.

        For a spell, this is equivalent to casting the spell. For a land,
        playing it is a special action that places the land on the battlefield.

        See :term:`playing` and :term:`cast` in the glossary.

        """

        self.game.require(started=True)

        if types.land in self.types:
            if self.owner.lands_this_turn < self.owner.lands_per_turn:
                self.owner.lands_this_turn += 1
                # TODO: event trigger?
                return self.game.battlefield.move(self)
            else:
                err = "{} cannot play another land this turn."
                raise exceptions.InvalidAction(err.format(self.owner))

        self.game.stack.add(Spell(self))
        self.game.events.trigger(  # XXX: isn't necessarily the right player
            event=events.CARD_CAST, card=self, player=self.owner,
        )


class Spell(object):
    """
    A spell is a card or copy of a card that is placed on the stack.

    """

    def __init__(self, card=None):
        super(Spell, self).__init__()

        self.card = card

    def __str__(self):
        return str(self.card)

    def __unicode__(self):
        return unicode(self.card)

    def __repr__(self):
        return "<Spell: {}>".format(self.card)


class Token(object):
    """
    A token is a marker for an object on the battlefield that is not a card.

    .. seealso::
        :ref:`tokens`

    """

    def __init__(self, name="", mana_cost="", colors=(), abilities=None,
                 types=(), subtypes=(), supertypes=(),
                 power=None, toughness=None, loyalty=None):

        super(Token, self).__init__()

        if abilities is None:
            abilities = {}

        self.name = name
        self.mana_cost = mana_cost
        self.colors = set(colors)
        self.abilities = list(abilities)
        self.types = set(types)
        self.subtypes, self.supertypes = set(subtypes), set(supertypes)
        self.power, self.toughness = power, toughness
        self.loyalty = loyalty

    @classmethod
    def from_card(cls, card, **new_characteristics):
        card_chars = characteristics(card)
        card_chars.update(**new_characteristics)
        return cls(**card_chars)


def characteristics(object_):
    """
    Get the :ref:`characteristics` of an M:TG :term:`object`.

    """

    CHARS = ["name", "mana_cost", "colors", "types", "subtypes", "supertypes",
             "abilities", "power", "toughness", "loyalty"]

    return {c : getattr(object_, c, None) for c in CHARS}


def converted_mana_cost(object_):
    """
    Calculate the :term:`converted mana cost` of an M:TG :term:`object`.

    """

    cost = 0

    if object_.mana_cost is not None:
        mana_cost = iter(object_.mana_cost)
        digits = []

        for d in mana_cost:
            if d.isdigit():
                digits.append(d)
            else:
                if d not in "XY":
                    cost += 1
                else:
                    if object_ in object_.game.stack:
                        cost += getattr(object_, d)
                cost += sum(1 for _ in mana_cost)  # XXX: Phyrex/Hybrid

        cost += int("".join(digits) or 0)

    return cost
