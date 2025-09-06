"""Handles fetching the current CGPA from the PESU Academy portal."""

import httpx
from bs4 import BeautifulSoup

from pesuacademy import constants


class _CGPAFetcher:
    """Handles fetching the current CGPA from the PESU Academy portal."""

    @staticmethod
    async def get_current_cgpa(session: httpx.AsyncClient) -> float | None:
        """Fetches the current CGPA from the My Placement Info page."""
        params = {"page": "my_placement_info"}  # Adjust param as per actual usage
        response = await session.get(constants.PAGES_BASE_URL, params=params)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        # Find the CGPA value in the span with id="cgpa"
        cgpa_span = soup.find("span", id="cgpa")
        if cgpa_span:
            try:
                return float(cgpa_span.text.strip())
            except ValueError:
                return None
        return None
