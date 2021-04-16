from showdown.battle import Battle

from ..helpers import format_decision

from showdown.engine.objects import StateMutator
from showdown.engine.select_best_move import pick_safest
from showdown.engine.select_best_move import get_payoff_matrix
from showdown.engine.select_best_move import pick_opponent_safest
from showdown.engine.select_best_move import get_opponent_payoff_matrix
from showdown.engine.helpers import normalize_name
from showdown.battle_bots.safest import prefix_opponent_move
from showdown.battle_bots.safest import pick_safest_move_from_battles

import config
import constants

import logging
logger = logging.getLogger(__name__)

LANDORUS_THERIAN = "landorustherian"
MAGEARNA = "magearna"
TAPU_KOKO = "tapukoko"
HAWLUCHA = "hawlucha"
DRAGAPULT = "dragapult"
KARTANA = "kartana"

# Perform logic for a specific Hyper Offense team where logic is determined by the current active Pokemon
# With more time I would create a way for the AI to determine the role of each Pokemon in the
# provided HO team and perform logic based on the role of the active Pokemon.
# Currently, the bot will not work if it is not using the provided dragapult_ho team in NatDex OU
class BattleBot(Battle):
    def __init__(self, *args, **kwargs):
        super(BattleBot, self).__init__(*args, **kwargs)

    def find_best_move(self):
        state = self.create_state()
        bot_options, opponent_options = self.get_all_options()

        bot_moves = []
        bot_switches = []
        for option in bot_options:
            if option.startswith(constants.SWITCH_STRING + " "):
                bot_switches.append(option)
            else:
                bot_moves.append(option)
        # Handle switch scenarios
        decision = None
        if self.force_switch or not moves:
            decision = self.handle_force_switch(state, bot_switches, opponent_options)

        # Handle scenario depending on the active Pokemon
        decision = self.decide_based_on_active(state, bot_options, bot_moves, bot_switches, opponent_options) if decision == None
        return format_decision(self, decision)

    def handle_force_switch(self, state, bot_switches, opponent_options):
        switch = bot_switches[0]
        if (self.user.last_used_move.turn == 0):
            return switch # Send out hazard setter on first turn
        
        # Logic for volt switch killing / double KO
        # Logic for volt switch happening first
        # Logic for volt switch happening second / bot Pokemon gets KOd

        return switch

    def decide_based_on_active(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        decision = bot_options[0]
        if (self.user.active.name == LANDORUS_THERIAN):
            decision = self.landorus_therian_logic(state, bot_options, bot_moves, bot_switches, opponent_options)
        elif (self.user.active.name == MAGEARNA):
            decision = self.magearna_logic(state, bot_options, bot_moves, bot_switches, opponent_options)
        elif (self.user.active.name == TAPU_KOKO):
            decision = self.tapu_koko_logic(state, bot_options, bot_moves, bot_switches, opponent_options)
        elif (self.user.active.name == HAWLUCHA):
            decision = self.hawlucha_logic(state, bot_options, bot_moves, bot_switches, opponent_options)
        elif (self.user.active.name == DRAGAPULT):
            decision = self.dragapult_logic(state, bot_options, bot_moves, bot_switches, opponent_options)
        else: # kartana
            decision = self.kartana_logic(state, bot_options, bot_moves, bot_switches, opponent_options)
        return decision

    # Suicide Lead - Prioritize setting up Stealth Rocks if not up, otherwise deal as much damage to
    # the currently active Pokemon as possible to avoid allowing them to set up. This logic should
    # ensure that when a Pokemon comes in that resists Landorus-Therian's Earthquake and Stone Edge,
    # it will use Explosion to allow another Pokemon to come in safely.
    def landorus_therian_logic(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        decision = bot_options[0]
        if (state.opponent.side_conditions[constants.STEALTH_ROCK] == 0) {
            decision = normalize_name("Stealth Rock")
        } else {
            most_damage = -1
            for move in bot_moves:
                damage_amounts = calculate_damage(state, constants.SELF, move, constants.DO_NOTHING_MOVE)

                damage = damage_amounts[0] if damage_amounts else 0

                if damage > most_damage:
                    decision = move
                    most_damage = damage
        }
        return decision

    # Mostly used as a damage sponge and pivot, but can be used to poke holes. Prioritize Volt Switch
    # for maintaining momentum.
    # 1) Opponent can do KO Magearna: safest move
    # 2) The opponent has a Ground type alive: most damaging move
    # 3) There is a move that can KO the currently active Pokemon: most damaging move
    # 4) Magearna currently has a boost: most damaging move
    # 5) Otherwise: volt switch
    # This logic is intended to be greedy in instances where a KO can be scored, and Volt Switch may
    # still be used in case 2 and 3 if it is the only move that can score a KO, for example.
    def magearna_logic(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        decision = bot_options[0]
        if (opponent_can_ko(state, opponent_options)):
            decision = default_to_safest_move()
        
        return decision

    # Use the opponent's safest move logic to try to determine if the opponent will switch. 
    # 1) If current Pokemon is Ground type and Tapu can't KO: safest move
    # 2) If they are likely to switch and they have no Ground type: Volt Switch
    # 3) If they can KO but Tapu can't KO back, safest move
    # 4) Otherwise, most damaging move. 
    # Basically, try to preserve momentum and poke holes when possible
    def tapu_koko_logic(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        decision = bot_options[0]
        return decision

    # Be greedy. Try to get a Swords Dance off and sweep / poke holes.
    # 1) If opponent safest option is switch: Swords Dance
    # 2) If can't KO opponent's active but opponent can KO Hawlucha: safest option
    # 3) If opponent isn't likely to switch but can't KO: Swords Dance
    # 4) Otherwise, most damaging move
    def hawlucha_logic(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        decision = bot_options[0]
        return decision

    # Like Hawlucha, be greedy and try to set up sweeps
    # Same logic as Hawlucha
    def dragapult_logic(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        decision = bot_options[0]
        return decision

    # Kartana's primary function is revenge killing fast Pokemon that could otherwise sweep the team.
    # Because of that, it's logic should focus on risk mitigation, and it should pretty much always
    # just use the move that will do the most damage to the currently active Pokemon. The only exception
    # is if Kartana can't KO the opponent but the opponent can KO it back, in which case go safest move.
    def kartana_logic(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        decision = bot_options[0]
        return decision

    def opponent_can_ko(self, state, opponent_options):
        can_ko = False
        for option in opponent_options:
            if not option.startswith(constants.SWITCH_STRING + " "):
                can_ko = calculate_damage(state, constants.OPPONENT, option, constants.DO_NOTHING_MOVE) >= state.user.active.hp
                return can_ko if can_ko
        return can_ko

    def default_to_safest_move(self):
        battles = self.prepare_battles(join_moves_together=True)
        safest_move = pick_safest_move_from_battles(battles)
        return safest_move
