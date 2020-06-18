import chess.pgn

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate, APITestCase

from .views import CreateGame, MovePiece, JoinGame
from .models import Game, Result
from chess_api_project.users.models import User



factory = APIRequestFactory()


class TestAPI(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user_one = User.objects.create_user(
            username='whitey_morgan', password='django')
        self.user_two = User.objects.create_user(
            username="blackie_lawless", password="django")

        self.create_view = CreateGame.as_view()
        self.move_piece_view = MovePiece.as_view()
        self.join_game_view = JoinGame.as_view()

    def _create_game(self, preferred_color="random"):
        data = {"preferred_color": preferred_color}
        request = factory.post("/chess/game/", data, format="json")
        force_authenticate(request, user=self.user_one)

        return request

    def _join_game(self, uuid, user, preferred_color="random"):
        data = {
            "uuid": uuid,
            "preferred_color": preferred_color,
        }

        join_request = factory.put("/chess/game/join/", data, format="json")
        force_authenticate(join_request, user=user)
        
        return join_request


    def test_can_create_game(self):
        """
        Create a game
        """

        game_request = self._create_game()
        response = self.create_view(game_request)

        self.assertIn("board", response.data)
        
    def test_can_retrieve_game(self):
        """
        Retrieve a game
        """
        game_request = self._create_game()
        create_response = self.create_view(game_request)

        get_request = factory.get("/chess/game/?uuid={uuid}".format(uuid=create_response.data.get("uuid")), format="json")
        force_authenticate(get_request, user=self.user_one)

        get_response = self.create_view(get_request)

        self.assertEqual(create_response.data.get('uuid'), get_response.data.get("uuid"))
        
    def test_can_join_game(self):
        """
        Test second user is able to join the game
        """

        game_request = self._create_game(preferred_color="white")
        game = self.create_view(game_request)

        join_request = self._join_game(game.data.get("uuid"), self.user_two)

        response = self.join_game_view(join_request)

        self.assertEqual(self.user_two.username, response.data.get(
            "blacks_player", {}).get("username"))

    def test_players_can_move_their_pieces(self):
        game_request = self._create_game(preferred_color="white")
        game = self.create_view(game_request)

        first_move = {
            "uuid": game.data.get("uuid"),
            "from_square": "e2",
            "to_square": "e4",
        }

        second_move = {
            "uuid": game.data.get("uuid"),
            "from_square": "e7",
            "to_square": "e5",
        }

        # First player (whites)
        request_whites = factory.put(
            "/chess/game/move/", first_move, format="json")

        force_authenticate(request_whites, user=self.user_one)

        response_whites = self.move_piece_view(request_whites)

        join_request = self._join_game(game.data.get("uuid"), self.user_two,
                        preferred_color="black")
        self.join_game_view(join_request)
        
        request_blacks = factory.put(
            "/chess/game/move/", second_move, format="json")

        force_authenticate(request_blacks, user=self.user_two)

        response_blacks = self.move_piece_view(request_blacks)

        self.assertIn("uuid", response_whites.data)
        self.assertIn("uuid", response_blacks.data)

    def test_players_can_only_move_pieces_they_own(self):
        game_request = self._create_game(preferred_color="white")
        response = self.create_view(game_request)
        
        # Attempt to move a black pawn as a white player
        move = {
            "uuid": response.data.get("uuid"),
            "from_square": "e7",
            "to_square": "e5",
        }

        request = factory.put(
            "/chess/game/move/", move, format="json")
        force_authenticate(request, user=self.user_one)

        response = self.move_piece_view(request)

        self.assertIn("detail", response.data)
        self.assertEqual("You can\'t move a piece at that square", response.data["detail"])

    def test_only_valid_moves_are_allowed(self):        
        game_request = self._create_game(preferred_color="white")
        response = self.create_view(game_request)

        # Attempt an illegal move
        move = {
            "uuid": response.data.get("uuid"),
            "from_square": "e2",
            "to_square": "e6",
        }
        
        request = factory.put(
            "/chess/game/move/", move, format="json")
        force_authenticate(request, user=self.user_one)

        response = self.move_piece_view(request)
        self.assertIn('message', response.data)
        self.assertEqual("{from_square}{to_square} is not a valid move.".format(
            from_square=move["from_square"], to_square=move["to_square"]
        ), response.data["message"])

    def test_non_player_users_cant_play(self):
        game_request = self._create_game(preferred_color="white")
        response = self.create_view(game_request)

        # Attempt to move a black pawn before joining the game
        move = {
            "uuid": response.data.get("uuid"),
            "from_square": "e5",
            "to_square": "e7",
        }

        request = factory.put(
            "/chess/game/move/", move, format="json")

        force_authenticate(request, user=self.user_two)
        response = self.move_piece_view(request)
        

        self.assertIn("detail", response.data)
        self.assertEqual("You can\'t move a piece at that square", response.data["detail"])
        
    def test_game_end(self):
        moves = []

        # Create board and game from PGN
        with open("api/pgn_games/fools_mate.pgn") as f:                
            game_pgn = chess.pgn.read_game(f)
            board = game_pgn.board()
            moves = [move for move in game_pgn.mainline_moves()]
            
        # Create game
        game_request = self._create_game(preferred_color="white")
        response = self.create_view(game_request)
        game_uuid = response.data.get("uuid")

        # Second player joins
        join_request = self._join_game(response.data.get("uuid"), self.user_two,
                        preferred_color="black")
        self.join_game_view(join_request)

        #Play all moves
        for counter, move in enumerate(moves):
            uci = move.uci()
            move = {
                "uuid": game_uuid,
                "from_square": uci[0:2],
                "to_square": uci[2:4],
            }

            request_move = factory.put(
                "/chess/game/move/", move, format="json")

            user = self.user_one if counter % 2 == 0 else self.user_two
            force_authenticate(request_move, user=user)            
                
            response_move = self.move_piece_view(request_move)        

        game = Game.objects.get(uuid=game_uuid)


        self.assertEqual(Result.BLACK_WINS, game.result.result)
        self.assertEqual(Result.NORMAL, game.result.termination)
        
        