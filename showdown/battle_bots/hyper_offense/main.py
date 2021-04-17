from showdown.battle import Battle

from ..helpers import format_decision

from random import randint
from data import all_move_json
from showdown.engine.objects import StateMutator
from showdown.engine.select_best_move import pick_safest
from showdown.engine.select_best_move import get_payoff_matrix
from showdown.engine.select_best_move import pick_opponent_safest
from showdown.engine.select_best_move import get_opponent_payoff_matrix
from showdown.engine.helpers import normalize_name
from showdown.engine.damage_calculator import calculate_damage
from showdown.battle_bots.safest.main import prefix_opponent_move
from showdown.battle_bots.safest.main import pick_safest_move_from_battles
from showdown.battle_bots.punish_opponent.main import prefix_opponent_move as punish_prefix_opponent_move
from showdown.battle_bots.punish_opponent.main import pick_safest_move_from_battles as punish_pick_safest_move_from_battles
from showdown.battle_bots.punish_opponent.main import prefix_user_move
from showdown.battle_bots.punish_opponent.main import pick_opponent_safest_move_from_battles

import config
import constants

import logging
logger = logging.getLogger(__name__)

LANDORUS_THERIAN = "landorustherian"
MAGNEZONE = "magnezone"
TAPU_KOKO = "tapukoko"
HAWLUCHA = "hawlucha"
DRAGAPULT = "dragapult"
KARTANA = "kartana"

ELECTRIC_IMMUNE = ["lightningrod", "voltabsorb", "motordrive"]
DANGEROUS_STATUS_MOVES = ["willowisp", "thunderwave", "spore", "haze", "roar", "whirlwind"]

# Perform logic for a specific Hyper Offense team where logic is determined by the current active Pokemon
# With more time I would create a way for the AI to determine the role of each Pokemon in the
# provided HO team and perform logic based on the role of the active Pokemon.
# Currently, the bot will not work if it is not using the provided dragapult_ho team in gen8ou
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
        if self.force_switch or not bot_moves:
            decision = self.handle_force_switch(state, bot_switches, opponent_options)

        # Handle scenario depending on the active Pokemon
        if decision == None:
            decision = self.decide_based_on_active(state, bot_options, bot_moves, bot_switches, opponent_options)
        return format_decision(self, decision)

    # Lead with the first Pokemon (Which will be the setter lead Landorus Therian)
    # Otherwise, choose the safest switch
    def handle_force_switch(self, state, bot_switches, opponent_options):
        switch = bot_switches[0]
        if (self.user.last_used_move.turn == 0):
            return switch # Send out hazard setter on first turn
        
        # Choose the safest switch in
        switch = self.pick_safest_move()

        return switch

    # Choose which logic to use based on which Pokemon is active
    def decide_based_on_active(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        decision = None
        if self.user.active.name == LANDORUS_THERIAN:
            logger.debug("Lando logic")
            decision = self.landorus_therian_logic(state, bot_options, bot_moves, bot_switches, opponent_options)
        elif self.user.active.name == MAGNEZONE:
            logger.debug("Mag logic")
            decision = self.magnezone_logic(state, bot_options, bot_moves, bot_switches, opponent_options)
        elif self.user.active.name == TAPU_KOKO:
            logger.debug("Tapu logic")
            decision = self.tapu_koko_logic(state, bot_options, bot_moves, bot_switches, opponent_options)
        elif self.user.active.name == HAWLUCHA:
            logger.debug("Lucha logic")
            decision = self.hawlucha_logic(state, bot_options, bot_moves, bot_switches, opponent_options)
        elif self.user.active.name == DRAGAPULT:
            logger.debug("Pult logic")
            decision = self.dragapult_logic(state, bot_options, bot_moves, bot_switches, opponent_options)
        else: # kartana
            logger.debug("Kart logic")
            decision = self.kartana_logic(state, bot_options, bot_moves, bot_switches, opponent_options)
        return decision

    # Suicide Lead - Prioritize setting up Stealth Rocks if not up, otherwise deal as much damage to
    # the currently active Pokemon as possible to avoid allowing them to set up. This logic should
    # ensure that when a Pokemon comes in that resists Landorus-Therian's Earthquake and Stone Edge,
    # it will use Explosion to allow another Pokemon to come in safely.
    def landorus_therian_logic(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        decision = None
        if state.opponent.side_conditions[constants.STEALTH_ROCK] == 0 and normalize_name("Stealth Rock") in bot_moves:
            logger.debug("Setting rocks")
            decision = normalize_name("Stealth Rock")
        else:
            logger.debug("Most Damaging Move")
            decision = self.pick_most_damaging_move(state, bot_moves)
        return decision

    # Mostly used as a damage sponge and pivot, but can be used to poke holes. Prioritize Volt Switch
    # for maintaining momentum.
    # 1) Opponent can do KO Magnezone: safest move
    # 2) The opponent has a Ground type/volt absorber alive: most damaging move
    # 3) There is a move that can KO the currently active Pokemon: most damaging move
    # 4) Otherwise: volt switch
    # This logic is intended to be greedy in instances where a KO can be scored
    # It may be worthwhile to add some randomness to the 2nd case, since opponents might predict an
    # attacking move and go into the Pokemon best suited to tank it instead of predicting volt switch
    def magnezone_logic(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        decision = None
        if self.side_can_ko(state, opponent_options, bot_side=False):
            logger.debug("Mag can get KO'd. Pick safest move.")
            decision = self.pick_safest_move()
        elif not self.safe_volt_switch(state) or self.side_can_ko(state, bot_options):
            logger.debug("Not safe to volt switch or can score a KO. Pick most damage.")
            decision = self.pick_most_damaging_move(state, bot_moves)
        elif normalize_name("Volt Switch") in bot_moves and len(state.self.get_switches()) > 0:
            logger.debug("Safe to Volt Switch")
            decision = normalize_name("Volt Switch")
        else: # Case where Volt Switch is out of PP and cannot be used (very rare)
            logger.debug("Volt Switch out of PP. Pick safest move.")
            decision = self.pick_safest_move()
        return decision

    # Try to be unpredictable between predicting the opponent's move and just hitting hard to poke
    # holes.
    def tapu_koko_logic(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        safe_or_punish = randint(0, 1)
        if safe_or_punish == 0:
            logger.debug("Picking safest move")
            decision = self.pick_safest_move()
        else:
            logger.debug("Picking move to punish opponent")
            decision = self.pick_punishing_move()
        return decision

    # Be greedy. Try to get a Swords Dance off and sweep / poke holes.
    # 1) If opponent safest move is Status move: Taunt
    # 2) If no boosts and can safely boost: Swords Dance
    # 3) If can't KO opponent's active but opponent can KO Hawlucha: safest option
    # 4) Otherwise, most damaging move
    def hawlucha_logic(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        decision = None
        opponent_safest = self.pick_opponent_safest_move()
        if self.should_taunt(opponent_safest, bot_moves):
            logger.debug("Opponent probably using statusn move. Taunting.")
            decision = normalize_name("Taunt")
        elif (self.safe_to_setup(state, opponent_options) and normalize_name("Swords Dance") in bot_moves 
        and not self.has_boost_and_can_2hko(state, bot_moves)):
            logger.debug("Safe to set up.")
            decision = normalize_name("Swords Dance")
        elif self.bot_loses_ko_trade(state, bot_options, opponent_options) or self.bot_loses_matchup(bot_options, opponent_options):
            logger.debug("Cannot KO before opponent can KO. Pick safest move.")
            decision = self.pick_safest_move()
        else:
            logger.debug("Trying to KO or sweep. Pick most damaging move.")
            decision = self.pick_most_damaging_move(state, bot_moves)
        return decision

    # Like Hawlucha, be greedy and try to set up sweeps
    # Same logic as Hawlucha, except no Taunt case
    def dragapult_logic(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        decision = None
        if (self.safe_to_setup(state, opponent_options) and normalize_name("Dragon Dance") in bot_moves
        and not self.has_boost_and_can_2hko(state, bot_moves)):
            logger.debug("Safe to set up.")
            decision = normalize_name("Dragon Dance")
        elif self.bot_loses_ko_trade(state, bot_options, opponent_options) or self.bot_loses_matchup(bot_options, opponent_options):
            logger.debug("Cannot KO before opponent can KO. Pick safest move.")
            decision = self.pick_safest_move()
        else:
            logger.debug("Trying to KO or sweep. Pick most damaging move.")
            decision = self.pick_most_damaging_move(state, bot_moves)
        return decision

    # Kartana's primary function is revenge killing fast Pokemon that could otherwise sweep the team.
    # Because of that, it's logic should focus on risk mitigation, and it should pretty much always
    # just use the move that will do the most damage to the currently active Pokemon. The only exception
    # is if Kartana can't KO the opponent but the opponent can KO it back, in which case go safest move.
    def kartana_logic(self, state, bot_options, bot_moves, bot_switches, opponent_options):
        decision = None
        if self.bot_loses_ko_trade(state, bot_options, opponent_options):
            logger.debug("Cannot KO before opponent can KO. Pick safest move.")
            decision = self.pick_safest_move()
        else:
            logger.debug("Trying to KO or sweep. Pick most damaging move.")
            decision = self.pick_most_damaging_move(state, bot_moves)
        return decision

    # Determine whether the specified active Pokemon can KO the other with an average damage calc
    def side_can_ko(self, state, options, bot_side=True):
        can_ko = False
        for option in options:
            if not option.startswith(constants.SWITCH_STRING + " "):
                if bot_side:
                    damage_amounts = calculate_damage(state, constants.SELF, option, constants.DO_NOTHING_MOVE) 
                    damage = damage_amounts[0] if damage_amounts else 0
                    can_ko = (damage >= state.opponent.active.hp)
                else:
                    damage_amounts = calculate_damage(state, constants.OPPONENT, option, constants.DO_NOTHING_MOVE)
                    damage = damage_amounts[0] if damage_amounts else 0
                    can_ko = (damage >= state.self.active.hp)           
            if can_ko:
                return can_ko
        return can_ko

    # Use the safest move logic to choose a move
    def pick_safest_move(self):
        battles = self.prepare_battles(join_moves_together=True)
        safest_move = pick_safest_move_from_battles(battles)
        return safest_move

    # Use the most damaging move logic to choose a move
    def pick_most_damaging_move(self, state, bot_moves):
        most_damage = -1
        decision = None
        for move in bot_moves:
            damage_amounts = calculate_damage(state, constants.SELF, move, constants.DO_NOTHING_MOVE)

            damage = damage_amounts[0] if damage_amounts else 0

            if damage > most_damage:
                decision = move
                most_damage = damage
        return decision
    
    # Use the opponent safest move logic to determine the opponent's safest move
    def pick_opponent_safest_move(self):
        battles = self.prepare_battles(join_moves_together=True)
        opponent_move = pick_opponent_safest_move_from_battles(battles)
        return opponent_move

    # Use the punish opponent logic to choose a move
    def pick_punishing_move(self):
        battles = self.prepare_battles(join_moves_together=True)
        safest_move = punish_pick_safest_move_from_battles(battles, list(), lookup_depth=config.search_depth)
        safest_move_list = [safest_move]
        opponent_move = pick_opponent_safest_move_from_battles(battles, safest_move_list)
        opponent_move_list = [opponent_move]
        most_punishing_move = punish_pick_safest_move_from_battles(battles, opponent_move_list, lookup_depth=config.search_depth)
        return most_punishing_move

    # Determine whether it is safe to use Volt Switch
    def safe_volt_switch(self, state):
        safe = True
        if self.pokemon_immune_to_electric(state.opponent.active):
            safe = False
        else:
            for pkmn_name, pkmn in state.opponent.reserve.items():
                if pkmn.hp > 0 and self.pokemon_immune_to_electric(pkmn):
                    safe = False
        return safe

    # Determine whether the given Pokemon is immune to electric type moves
    def pokemon_immune_to_electric(self, pkmn):
        return pkmn.ability in ELECTRIC_IMMUNE or "ground" in pkmn.types

    # Determine whether Taunt should be used
    def should_taunt(self, opponent_safest, bot_moves):
        return (not opponent_safest.startswith(constants.SWITCH_STRING + " ") 
        and all_move_json[opponent_safest].get(constants.CATEGORY) == constants.STATUS 
        and normalize_name("Taunt") in bot_moves)
    
    # Determine whether it is safe to use a set up move to prepare to sweep or wall break
    def safe_to_setup(self, state, opponent_options):
        safe = False
        opponent_safest = self.pick_opponent_safest_move()
        if opponent_safest.startswith(constants.SWITCH_STRING + " "):
            safe = True
        elif (not opponent_safest in DANGEROUS_STATUS_MOVES) and (not self.side_can_ko(state, opponent_options, bot_side=False)):
            logger.debug("Opponent can't status or KO")
            safe = True
        return safe

    # Determine whether the bot can KO, but would get KO'd first by a faster Pokemon
    # Bot should play aggresively, so go for the KO even if there's a speed tie
    def bot_loses_ko_trade(self, state, bot_options, opponent_options):
        return (self.side_can_ko(state, opponent_options, bot_side=False) 
        and self.side_can_ko(state, bot_options)
        and state.self.active.speed < state.opponent.active.speed)

    # Determine whether the bot's active Pokemon would get KO'd and be unable to KO the opponent's active
    def bot_loses_matchup(self, bot_options, opponent_options):
        return self.side_can_ko(state, opponent_options, bot_side=False) and not self.side_can_ko(state, bot_options)

    # Determine whether the bot's active Pokemon has boosts and can KO the opponent's active in two attacks
    def has_boost_and_can_2hko(self, state, bot_moves):
        most_damage = self.pick_most_damaging_move(state, bot_moves)
        damage_amounts = calculate_damage(state, constants.SELF, most_damage, constants.DO_NOTHING_MOVE)
        damage = damage_amounts[0] if damage_amounts else 0
        return self.has_offensive_boost(state.self.active) and damage * 2 >= state.opponent.active.hp

    # Determine if the bot's active Pokemon has boosts in offensive stats
    def has_offensive_boost(self, pkmn):
        return (pkmn.attack_boost > 0 or pkmn.special_attack_boost > 0