from showdown.battle import Battle

from ..helpers import format_decision

from showdown.engine.objects import StateMutator
from showdown.engine.select_best_move import pick_safest
from showdown.engine.select_best_move import get_payoff_matrix
from showdown.engine.select_best_move import pick_opponent_safest
from showdown.engine.select_best_move import get_opponent_payoff_matrix

import config

import logging
logger = logging.getLogger(__name__)


def prefix_opponent_move(score_lookup, prefix):
    new_score_lookup = dict()
    for k, v in score_lookup.items():
        bot_move, opponent_move = k
        new_opponent_move = "{}_{}".format(opponent_move, prefix)
        new_score_lookup[(bot_move, new_opponent_move)] = v

    return new_score_lookup

# Pick safest move from battles that takes a list of moves for the user instead of generating it if given one
def pick_safest_move_from_battles(battles, possible_moves, lookup_depth=1):
    all_scores = dict()
    for i, b in enumerate(battles):
        state = b.create_state()
        mutator = StateMutator(state)
        user_options, opponent_options = b.get_all_options()
        logger.debug("Searching through the state for safest move: {}".format(mutator.state))
        if len(possible_moves) > 0:
            scores = get_payoff_matrix(mutator, user_options, possible_moves, depth = lookup_depth, prune=True)
        else:
            scores = get_payoff_matrix(mutator, user_options, opponent_options, depth = lookup_depth, prune=True)
        prefixed_scores = prefix_opponent_move(scores, str(i))
        all_scores = {**all_scores, **prefixed_scores}

    decision, payoff = pick_safest(all_scores)
    bot_choice = decision[0]
    logger.debug("Safest: {}, {}".format(bot_choice, payoff))
    return bot_choice

# Altered the logic of prefix opponent move to prefix user move for picking opponent's safest move
def prefix_user_move(score_lookup, prefix):
    new_score_lookup = dict()
    for k, v in score_lookup.items():
        bot_move, opponent_move = k
        new_bot_move = "{}_{}".format(bot_move, prefix)
        new_score_lookup[(opponent_move, new_bot_move)] = v

    return new_score_lookup

# Altered the logic of the pick safest moves from battles method for determining the opponent's safest move
def pick_opponent_safest_move_from_battles(battles, player_safest_move=None, lookup_depth=1):
    all_scores = dict()
    for i, b in enumerate(battles):
        state = b.create_state()
        mutator = StateMutator(state)
        user_options, opponent_options = b.get_all_options()
        if player_safest_move == None:
            player_safest_move = user_options
        logger.debug("Searching through the state for opponent safest move: {}".format(mutator.state))
        scores = get_opponent_payoff_matrix(mutator, player_safest_move, opponent_options, depth=lookup_depth, prune=True)

        prefixed_scores = prefix_opponent_move(scores, str(i))
        all_scores = {**all_scores, **prefixed_scores}
    
    decision, payoff = pick_opponent_safest(all_scores)
    bot_prediction = decision[0]
    logger.debug("Opponent Safest: {}, {}".format(bot_prediction, payoff))
    return bot_prediction


# Find player's safest move
# Find opponent's safest move if player makes safest move
# Find player's safest move if opponent makes that move
class BattleBot(Battle):
    def __init__(self, *args, **kwargs):
        super(BattleBot, self).__init__(*args, **kwargs)

    def find_best_move(self):
        battles = self.prepare_battles(join_moves_together=True)
        safest_move = pick_safest_move_from_battles(battles, list(), lookup_depth=config.search_depth)
        safest_move_list = [safest_move]
        opponent_move = pick_opponent_safest_move_from_battles(battles, safest_move_list)
        opponent_move_list = [opponent_move]
        most_punishing_move = pick_safest_move_from_battles(battles, opponent_move_list, lookup_depth=config.search_depth)
        return format_decision(self, most_punishing_move)