"""Presentation reservation uses the IDE display lock, without device I/O."""

import asyncio

from ninjarobot_pi5_ide.display import DisplayDevice
from PIL import Image


def test_waiting_qr_survives_late_faces_and_safety_has_precedence() -> None:
    async def exercise() -> None:
        display = DisplayDevice(simulated=True)
        await display.start()
        width, height = await display.dimensions()
        image = Image.new("RGB", (width, height))
        assert await display.set_waiting_presentation(2, True)
        assert "suppressed" not in await display.show_image(image, source="phase-8-onboarding-qr")
        assert "suppressed" in await display.show_image(image, source="face:idle")
        assert "suppressed" in await display.clear(color="#000000")
        assert "suppressed" not in await display.show_image(image, source="safety:emergency-stop")
        assert not await display.set_waiting_presentation(1, False)
        assert "suppressed" in await display.show_image(image, source="face:speaking")
        assert await display.set_waiting_presentation(3, False)
        assert "suppressed" not in await display.show_image(image, source="face:idle")
        await display.close()

    asyncio.run(exercise())


def test_safety_and_active_privacy_defer_even_late_qr_frames() -> None:
    async def exercise() -> None:
        display = DisplayDevice(simulated=True)
        await display.start()
        size = await display.dimensions()
        image = Image.new("RGB", size)
        await display.set_waiting_presentation(1, True)
        await display.set_safety_presentation(True)
        assert "suppressed" in await display.show_image(image, source="phase-8-onboarding-qr")
        assert "suppressed" not in await display.show_image(image, source="safety:warning")
        await display.set_safety_presentation(False)
        await display.set_privacy_presentation(True)
        assert "suppressed" in await display.show_image(image, source="phase-8-onboarding-qr")
        assert "suppressed" not in await display.show_image(image, source="privacy:camera")
        await display.set_privacy_presentation(False)
        assert "suppressed" not in await display.show_image(image, source="phase-8-onboarding-qr")
        await display.close()

    asyncio.run(exercise())
