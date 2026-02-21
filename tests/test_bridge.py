import unittest
import os
import shutil
import tempfile
import sys

# Add parent directory to path to import bridge_server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge_server import route_message, append_to_history, get_history, AGENT_ROUTING, HISTORY_DIR

class TestBridgeLogic(unittest.TestCase):
    
    def setUp(self):
        # Create a temporary directory for history tests
        self.test_dir = tempfile.mkdtemp()
        # Mock the HISTORY_DIR in the module (if possible, or just rely on file ops if we could patch)
        # Since standard import doesn't allow easy constant patching without reload, 
        # let's just test the logic functions that shouldn't depend on global state if possible.
        # However, append_to_history uses global HISTORY_DIR. 
        # We will monkey-patch the module variable for this test context.
        import bridge_server
        self.original_history_dir = bridge_server.HISTORY_DIR
        bridge_server.HISTORY_DIR = self.test_dir

    def tearDown(self):
        # Restore and cleanup
        import bridge_server
        bridge_server.HISTORY_DIR = self.original_history_dir
        shutil.rmtree(self.test_dir)

    def test_route_message_coder(self):
        """Test routing to coder agent."""
        msg = "Please write a python function."
        self.assertEqual(route_message(msg), "coder")
        
        msg = "fix this bug for me"
        self.assertEqual(route_message(msg), "coder")

    def test_route_message_reviewer(self):
        """Test routing to reviewer agent."""
        msg = "Please review my code."
        self.assertEqual(route_message(msg), "reviewer")
        
        msg = "check this pr"
        self.assertEqual(route_message(msg), "reviewer")

    def test_route_message_default(self):
        """Test routing to default agent."""
        msg = "Hello current world"
        self.assertEqual(route_message(msg), "defaults")

    def test_history_read_write(self):
        """Test writing and reading shared history."""
        chat_id = "12345"
        sender = "User1"
        message = "Hello Bot"
        
        # Write
        import bridge_server
        bridge_server.append_to_history(chat_id, sender, message)
        
        # Verify file exists
        expected_file = os.path.join(self.test_dir, f"{chat_id}.txt")
        self.assertTrue(os.path.exists(expected_file))
        
        # Read
        content = bridge_server.get_history(chat_id)
        self.assertIn(f"[{sender}]: {message}", content)

    def test_routing_keywords(self):
        """Ensure all keywords in config map correctly."""
        for agent, keywords in AGENT_ROUTING.items():
            for keyword in keywords:
                self.assertEqual(route_message(f"I want to {keyword} something"), agent, f"Keyword '{keyword}' failed")

if __name__ == '__main__':
    unittest.main()
