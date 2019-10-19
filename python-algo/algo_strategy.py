import gamelib
import random
import math
import warnings
from sys import maxsize
import json
import operator


"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global FILTER, ENCRYPTOR, DESTRUCTOR, PING, EMP, SCRAMBLER, BITS, CORES
        FILTER = config["unitInformation"][0]["shorthand"]
        ENCRYPTOR = config["unitInformation"][1]["shorthand"]
        DESTRUCTOR = config["unitInformation"][2]["shorthand"]
        PING = config["unitInformation"][3]["shorthand"]
        EMP = config["unitInformation"][4]["shorthand"]
        SCRAMBLER = config["unitInformation"][5]["shorthand"]
        BITS = 0
        CORES = 1
        # This is a good place to do initial setup
        self.scored_on_locations = []

        # Decrement cost of a state by this much when it hits our boundary
        self.damaged_cost_decrement = 50
        self.left_enemy_edge = [(x, x + 14) for x in range(14)]
        self.right_enemy_edge = [(i + 14, 27 - i) for i in range(14)]
        self.enemy_attacker_spawn_locations = self.left_enemy_edge + self.right_enemy_edge

        # Create the Value map for Value Iteration
        self.map_values = {(x, y) : 0 for y in range(14) for x in range(13 - y, 15 + y)}


    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.

        self.defense_offense_strategy(game_state)

        game_state.submit_turn()

    """
        NOTE: All the methods after this point are part of the sample starter-algo
        strategy and can safely be replaced for your custom algo.
    """

    def defense_offense_strategy(self, game_state):
        """
                For defense we will use a spread out layout and some Scramblers early on.
                We will place destructors near locations the opponent managed to score on.
                For offense we will use long range EMPs if they place stationary units near the enemy's front.
                If there are no stationary units to attack in the front, we will send Pings to try and score quickly.
                """
        # --- DEFENSE --- #
        # First, update the map
        self.update_map(game_state)
        self.value_iteration(game_state, 0.9, 100)
        # First, place basic defenses
        self.spawn_defense(game_state)

        # --- OFFENSE --- #
        self.send_pings_if_survive(game_state)
        self.send_emp(game_state)
        self.send_scramblers(game_state)


    def value_iteration(self, game_state, discount, iterations):
        # create value_map
        np1Values = {(x, y) : 0 for y in range(14) for x in range(13 - y, 15 + y)}

        for __ in range(iterations):
            for s in game_state.get_defensive_states():
                np1Values[s] = self.map_values[s] + discount * \
                        max([self.map_values[a] for a in
                        game_state.get_possible_actions([s[0], s[1]])])
            self.map_values = np1Values.copy()

    def spawn_defense(self, game_state):
        # friendly edges
        friendly_edges = game_state.game_map.get_edge_locations(
            game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(
            game_state.game_map.BOTTOM_RIGHT)

        # spawn defenses
        for s in sorted(self.map_values.items(), key=operator.itemgetter(1)):
            if s not in friendly_edges and game_state.get_resource(CORES) > 0:
                game_state.attempt_spawn(DESTRUCTOR, [s[0], s[1]])
    #     spawn defense

    def send_pings_if_survive(self, game_state):
        possibleSpawnLocations = game_state.game_map.get_edge_locations(
                game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(
                game_state.game_map.BOTTOM_RIGHT)
        location = self.least_damage_spawn_location(game_state,
                self.filter_blocked_locations(possibleSpawnLocations, game_state))
        numPings = math.floor(game_state.get_resource(BITS) / game_state.type_cost(PING))
        if self.does_survive(game_state, location, numPings):
            for _ in range(numPings):
                game_state.attempt_spawn(PING, location)

    def does_survive(self, game_state, location, numPings):
        path = game_state.find_path_to_edge(location)
        damage = 0
        for path_location in path:
            # Get number of enemy destructors that can attack the final location and multiply by destructor damage
            damage += len(
                game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(
                DESTRUCTOR, game_state.config).damage
        return numPings - damage > 0

    def send_scramblers(self, game_state):
        possibleSpawnLocations = game_state.game_map.get_edge_locations(
                game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(
                game_state.game_map.BOTTOM_RIGHT)
        location = self.least_damage_spawn_location(game_state,
                self.filter_blocked_locations(possibleSpawnLocations, game_state))
        numScrambler = math.floor(game_state.get_resource(BITS) / game_state.type_cost(SCRAMBLER))
        for _ in range(numScrambler):
            game_state.attempt_spawn(SCRAMBLER, location)

    def send_emp(self, game_state):
        possibleSpawnLocations = game_state.game_map.get_edge_locations(
                game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(
                game_state.game_map.BOTTOM_RIGHT)
        location = self.least_damage_spawn_location(game_state,
                self.filter_blocked_locations(possibleSpawnLocations, game_state))
        numEMP = math.floor(game_state.get_resource(BITS) / game_state.type_cost(EMP))
        for _ in range(numEMP):
            game_state.attempt_spawn(numEMP, location)


    def update_map(self, game_state):
        # For every location along the barrier that was struck, we decrease the value by 100
        for location in self.scored_on_locations:
            self.map_values[(location[0], location[1])] -= self.damaged_cost_decrement

        for location in self.enemy_attacker_spawn_locations:
            path = game_state.find_path_to_edge([location[0], location[1]])
            damage = 0
            for path_location in path:
                # Adding damage done by all destructors that can attack that location
                damage += len(game_state.get_attackers(path_location, 1)) * \
                            gamelib.GameUnit(DESTRUCTOR, game_state.config).damage

                damage += len(game_state.get_attackers_encryptors(path_location, 1)) * \
                          gamelib.GameUnit(ENCRYPTOR, game_state.config).damage

                if (path_location[0], path_location[1]) in self.map_values:
                    self.map_values[(path_location[0], path_location[1])] -= damage


    def stall_with_scramblers(self, game_state):
        """
        Send out Scramblers at random locations to defend our base from enemy moving units.
        """
        # We can spawn moving units on our edges so a list of all our edge locations
        friendly_edges = game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT)

        # Remove locations that are blocked by our own firewalls
        # since we can't deploy units there.
        deploy_locations = self.filter_blocked_locations(friendly_edges, game_state)

        # While we have remaining bits to spend lets send out scramblers randomly.
        while game_state.get_resource(BITS) >= game_state.type_cost(SCRAMBLER) and len(deploy_locations) > 0:
            # Choose a random deploy location.
            deploy_index = random.randint(0, len(deploy_locations) - 1)
            deploy_location = deploy_locations[deploy_index]

            game_state.attempt_spawn(SCRAMBLER, deploy_location)
            """
            We don't have to remove the location since multiple information 
            units can occupy the same space.
            """

    def emp_line_strategy(self, game_state):
        """
        Build a line of the cheapest stationary unit so our EMP's can attack from long range.
        """
        # First let's figure out the cheapest unit
        # We could just check the game rules, but this demonstrates how to use the GameUnit class
        stationary_units = [FILTER, DESTRUCTOR, ENCRYPTOR]
        cheapest_unit = FILTER
        for unit in stationary_units:
            unit_class = gamelib.GameUnit(unit, game_state.config)
            if unit_class.cost < gamelib.GameUnit(cheapest_unit, game_state.config).cost:
                cheapest_unit = unit

        # Now let's build out a line of stationary units. This will prevent our EMPs from running into the enemy base.
        # Instead they will stay at the perfect distance to attack the front two rows of the enemy base.
        for x in range(27, 5, -1):
            game_state.attempt_spawn(cheapest_unit, [x, 11])

        # Now spawn EMPs next to the line
        # By asking attempt_spawn to spawn 1000 units, it will essentially spawn as many as we have resources for
        game_state.attempt_spawn(EMP, [24, 10], 1000)

    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy destructors that can attack the final location and multiply by destructor damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(DESTRUCTOR, game_state.config).damage
            damages.append(damage)
        
        # Now just return the location that takes the least damage
        return location_options[damages.index(min(damages))]

    def detect_enemy_unit(self, game_state, unit_type=None, valid_x = None, valid_y = None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units
        
    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at: https://docs.c1games.com/json-docs.html
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly, 
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                gamelib.debug_write("All locations: {}".format(self.scored_on_locations))


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
