"""
Scouting App for Team 334
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW


class Castle(toga.App):
    def startup(self):
        """Construct and show the Toga application.

        Usually, you would add your application to a main content box.
        We then create a main window (with a name matching the app), and
        show the main window.
        """
        # Completely clear the command set to remove all menus
        self._impl.create_menus = lambda *x, **y: None
        
        # Create the main box with a COLUMN direction
        main_box = toga.Box(style=Pack(direction=COLUMN, flex=1))
        
        # Create the WebView
        web_view = toga.WebView(
            style=Pack(flex=1),
            url='https://castlescouting.com'
        )
        
        # Add the WebView to the main box
        main_box.add(web_view)

        # Create the main window and set its content
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()


def main():
    return Castle()
