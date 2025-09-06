"""PESU Academy Scraper Client."""

import asyncio

import httpx
from bs4 import BeautifulSoup

from pesuacademy.models import (
    Announcement,
    Course,
    MaterialLink,
    Profile,
    SeatingInformation,
    SemesterResult,
    Timetable,
    Topic,
    Unit,
)
from pesuacademy.pages import (
    _AnnouncementPageHandler,
    _AttendancePageHandler,
    _CourseDetailPageHandler,
    _CoursesPageHandler,
    _MaterialLinksHandler,
    _ProfilePageHandler,
    _ResultsPageHandler,
    _SeatingInformationHandler,
    _SemesterHandler,
    _TimetablePageHandler,
    _UnitPageHandler,
)


class _PesuScraper:
    def __init__(self) -> None:
        """Initializes the PESU Academy scraper with a base URL and an HTTP session."""
        self._base_url = "https://www.pesuacademy.com/Academy"
        self._session = httpx.AsyncClient(base_url=self._base_url, follow_redirects=True, timeout=30.0)
        self._csrf_token: str | None = None
        self._semester_ids: dict[int, str] = {}

    async def login(self, username: str, password: str) -> None:
        """Logs in to the PESU Academy portal and initializes the session.

        Args:
            username (str): The user's SRN, PRN, or other login identifier.
            password (str): The user's password.

        Raises:
            Exception: If the login fails or the credentials are invalid.

        Returns:
            None
        """
        response = await self._session.get("/")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        # Extract the CSRF token from the initial page
        initial_csrf = soup.find("meta", attrs={"name": "csrf-token"})["content"]

        login_data = {
            "_csrf": initial_csrf,
            "j_username": username,
            "j_password": password,
        }
        response = await self._session.post("/j_spring_security_check", data=login_data)
        response.raise_for_status()

        if "Invalid credentials" in response.text:  # Check if login failed
            raise Exception("Authentication failed. Please check your credentials.")

        # After login, fetch the CSRF token again
        soup = BeautifulSoup(response.text, "lxml")
        final_csrf = soup.find("meta", attrs={"name": "csrf-token"})["content"]
        self._csrf_token = final_csrf
        # Always Fetch semester IDs after successful login
        # Improve this by making it a separate method later
        self._semester_ids = await _SemesterHandler._get_semester_ids(self._session)

    async def get_seating_info(self) -> list[SeatingInformation]:
        return await _SeatingInformationHandler._get(self._session)

    async def get_profile(self) -> Profile:
        return await _ProfilePageHandler._get(self._session)

    async def get_courses(self, semester: int | None = None) -> dict[int, list[Course]]:
        # Fetch courses for a specific semester or all semesters if none specified
        semesters_to_fetch = (
            {semester: self._semester_ids[semester]}
            if semester and semester in self._semester_ids
            else self._semester_ids
        )
        tasks = [_CoursesPageHandler._get(self._session, sem_id) for sem_id in semesters_to_fetch.values()]
        results = await asyncio.gather(*tasks)
        return dict(zip(semesters_to_fetch.keys(), results))

    async def get_attendance(self, semester: int | None = None) -> dict[int, list[Course]]:
        # Fetch attendance for a specific semester or all semesters if none specified
        semesters_to_fetch = (
            {semester: self._semester_ids[semester]}
            if semester and semester in self._semester_ids
            else self._semester_ids
        )
        tasks = [_AttendancePageHandler._get(self._session, sem_id) for sem_id in semesters_to_fetch.values()]
        results = await asyncio.gather(*tasks)
        return dict(zip(semesters_to_fetch.keys(), results))

    async def _get_placement_info_url(self) -> str | None:
        """Extracts the placement info URL from the menu after login."""
        response = await self._session.get("/")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        menu_item = soup.find("li", attrs={"data-url": lambda v: v and "placementinfo" in v})
        if menu_item:
            return menu_item.get("data-url")
        return None

    async def get_current_cgpa(self) -> float | None:
        """Fetches the current CGPA from the My Placement Info page."""
        path = await self._get_placement_info_url()
        if not path:
            return None
        # Fetch the placement info page directly (AJAX endpoint)
        response = await self._session.get(f"/{path}")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        # Try to find the CGPA in a span or in a table
        cgpa_span = soup.find("span", id="cgpa")
        if cgpa_span:
            try:
                return float(cgpa_span.text.strip())
            except ValueError:
                return None
        # Fallback: look for "CGPA" in table rows
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2 and "CGPA" in cells[0].get_text():
                try:
                    return float(cells[1].get_text().strip())
                except ValueError:
                    continue
        return None

    async def get_announcements(self) -> list[Announcement]:
        return await _AnnouncementPageHandler._get(self._session)

    async def get_units_for_course(self, course_id: str) -> list[Unit]:
        return await _CourseDetailPageHandler._get(self._session, course_id)

    async def get_topics_for_unit(self, unit_id: str) -> list[Topic]:
        return await _UnitPageHandler._get(self._session, unit_id)

    async def get_material_links(self, topic: Topic, material_type_id: str) -> list[MaterialLink]:
        return await _MaterialLinksHandler._get(self._session, topic, material_type_id)

    async def get_results(self, semester_id: str) -> SemesterResult:
        return await _ResultsPageHandler._get(self._session, semester_id)

    async def get_timetable(self) -> Timetable:
        return await _TimetablePageHandler._get(self._session)

    async def close(self) -> None:
        await self._session.aclose()
