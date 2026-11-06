import numpy as np
import pytest

import f1_search_frame as search


LAP_STARTS = [194.277, 270.787, 364.798]
OBSERVED_LAP_DIGIT_ROWS = {
    0: (
        "........",
        "........",
        "..####..",
        ".######.",
        ".##..##.",
        ".######.",
        ".###.##.",
        ".##..##.",
        ".######.",
        "..####..",
        "........",
        "........",
    ),
    1: (
        "........",
        "........",
        "..##....",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "...##...",
        "..####..",
        "........",
        "........",
    ),
    2: (
        "........",
        "........",
        "..####..",
        "..#####.",
        "....###.",
        "...###..",
        "..###...",
        ".###....",
        ".#####..",
        "..####..",
        "........",
        "........",
    ),
    3: (
        "........",
        "........",
        "..####..",
        "..####..",
        "....##..",
        "..####..",
        "..####..",
        "....##..",
        "..####..",
        "..###...",
        "........",
        "........",
    ),
}


def observed_lap_digit_mask(digit):
    return search.digit_rows_to_mask(OBSERVED_LAP_DIGIT_ROWS[digit])


def test_lap_navigation_from_between_starts():
    assert search.next_lap_start(LAP_STARTS, 300, 0.008) == 364.798
    assert search.previous_lap_start(LAP_STARTS, 300, 0.008) == 270.787


def test_lap_navigation_on_a_start_steps_to_the_neighbour():
    assert search.next_lap_start(LAP_STARTS, 270.787, 0.008) == 364.798
    assert search.previous_lap_start(LAP_STARTS, 270.787, 0.008) == 194.277


def test_lap_navigation_stops_at_the_ends():
    assert search.previous_lap_start(LAP_STARTS, 0, 0.008) is None
    assert search.next_lap_start(LAP_STARTS, 364.798, 0.008) is None


def test_lap_under_playhead_spans_the_lap_containing_the_time():
    assert search.lap_under_playhead(LAP_STARTS, 300, 500) == (1, 270.787, 364.798, 3)
    assert search.lap_under_playhead(LAP_STARTS, 270.787, 500) == (1, 270.787, 364.798, 3)
    assert search.lap_under_playhead(LAP_STARTS, 0, 500) == (None, 0.0, 194.277, 3)
    assert search.lap_under_playhead(LAP_STARTS, 400, 500) == (2, 364.798, 500, 3)


def test_lap_under_playhead_keeps_a_rounded_down_start_frame():
    assert search.lap_under_playhead(LAP_STARTS, 270.783, 500, half_frame=0.008) == (
        1, 270.787, 364.798, 3,
    )
    assert search.lap_under_playhead(LAP_STARTS, 270.783, 500) == (0, 194.277, 270.787, 3)


def test_lap_under_playhead_requires_a_start_inside_the_video():
    assert search.lap_under_playhead([], 10, 500) is None
    assert search.lap_under_playhead(LAP_STARTS, 10, 0) is None
    assert search.lap_under_playhead([600], 10, 500) is None


def test_lap_frame_bounds_stop_before_the_next_lap():
    assert search.lap_frame_bounds(10.0, 11.0, 60, 10000) == (600, 659)


def test_lap_frame_bounds_keep_a_short_lap_on_one_frame():
    assert search.lap_frame_bounds(10.0, 10.001, 60, 10000) == (600, 600)


def test_lap_frame_bounds_reject_a_non_positive_rate():
    with pytest.raises(ValueError, match="fps must be positive"):
        search.lap_frame_bounds(0, 1, 0, 10)


def test_lap_scrub_caption_names_the_lap_and_the_offset():
    assert search.lap_scrub_caption(1, 3, 300, 270.787, 364.798) == "Lap 2/3  00:29.213 / 01:34.011"
    assert search.lap_scrub_caption(None, 3, 12.5, 0, 194.277) == "Before laps  00:12.500 / 03:14.277"


def test_lap_digit_templates_match_themselves_and_stay_apart():
    masks = {digit: search.lap_digit_template(digit) for digit in (0, 1, 2, 3)}
    for digit, mask in masks.items():
        assert search.lap_digit_distance(mask, mask) == 0
        assert search.match_lap_digit(mask) == digit
    for left in range(4):
        for right in range(left + 1, 4):
            assert search.lap_digit_distance(masks[left], masks[right]) >= 11
    assert search.lap_digit_distance(masks[0], masks[1]) == 31
    assert search.lap_digit_distance(masks[2], masks[3]) == 11


def test_observed_lap_glyphs_match_their_digits():
    for digit in range(4):
        mask = observed_lap_digit_mask(digit)
        own_distance = search.lap_digit_distance(mask, search.lap_digit_template(digit))
        assert own_distance == 0
        assert search.match_lap_digit(mask) == digit
        for other in range(4):
            if other == digit:
                continue
            other_distance = search.lap_digit_distance(mask, search.lap_digit_template(other))
            assert other_distance >= own_distance + 4


def test_observed_glyph_plus_one_produces_a_lap_start():
    samples = []
    time_seconds = 10.0
    for digit in range(4):
        samples.append((time_seconds, search.match_lap_digit(observed_lap_digit_mask(digit))))
        time_seconds += 5.0
    brackets = search.lap_brackets_from_digits(samples)
    assert [bracket[2] for bracket in brackets] == [1, 2, 3]
    for _previous_time, new_time, new_digit in brackets:
        frames = [
            (new_time + index / 50, new_digit)
            for index in range(search.LAP_DIGIT_HOLD_FRAMES)
        ]
        assert search.held_lap_start_time(frames, new_digit) == new_time


def test_lap_digit_match_accepts_distance_four_and_rejects_five():
    near = search.lap_digit_template(2).copy()
    flat = near.reshape(-1)
    flat[:4] = ~flat[:4]
    assert search.lap_digit_distance(near, search.lap_digit_template(2)) == 4
    assert search.match_lap_digit(near) == 2

    flat[4] = ~flat[4]
    assert search.lap_digit_distance(near, search.lap_digit_template(2)) == 5
    assert search.match_lap_digit(near) is None


def test_lap_brackets_from_digits():
    assert search.lap_brackets_from_digits([(10, 0), (15, 1)]) == [(10, 15, 1)]
    assert search.lap_brackets_from_digits([(100, 3), (106, 3)]) == []
    assert search.lap_brackets_from_digits([(0, None), (200, 1)]) == []
    assert search.lap_brackets_from_digits([(10, 1), (40, None), (50, 2)]) == []
    assert search.lap_brackets_from_digits([(10, 2), (16, 3)]) == [(10, 16, 3)]
    assert search.lap_brackets_from_digits([(10, 3), (16, 0)]) == []


def test_one_missed_keyframe_still_brackets_the_step():
    samples = [(10, 0), (15, None), (20, 1)]
    assert search.lap_brackets_from_digits(samples) == [(10, 20, 1)]


def test_five_frame_hold_returns_the_first_frame_of_the_run():
    frames = [(0.0, 1), (0.1, 2), (0.2, 2), (0.3, 2), (0.4, 2)]
    assert search.held_lap_start_time(frames, 2) is None
    frames.append((0.5, 2))
    assert search.held_lap_start_time(frames, 2) == 0.1


def test_single_frame_digit_blip_is_not_a_hold():
    frames = [(0.0, 1), (0.1, 2), (0.2, 1)]
    assert search.held_lap_start_time(frames, 2) is None


def test_lap_letter_presence():
    assert search.is_lap_letter_present(107, 0.82) is True
    assert search.is_lap_letter_present(0, 0.82) is False
    assert search.is_lap_letter_present(240, 0.82) is False
    assert search.is_lap_letter_present(313, 0.18) is False


def test_lap_crop_at_reference_size():
    assert search.lap_crop_for_frame(1920, 1080) == (80, 28, 164, 128)


def blank_timer():
    return np.zeros((search.TIMER_CROP_HEIGHT, search.TIMER_CROP_WIDTH), dtype=np.uint8)


def test_timer_glyph_states():
    dashes = blank_timer()
    dashes[10, 47:81] = 255
    assert search.timer_glyph_state(dashes) == "dashes"

    long_time = blank_timer()
    long_time[3:15, 10:30] = 255
    assert search.timer_glyph_state(long_time) == "long"

    short_time = blank_timer()
    short_time[3:15, 43:58] = 255
    assert search.timer_glyph_state(short_time) == "short"

    mid_time = blank_timer()
    mid_time[3:15, 29:47] = 255
    assert search.timer_glyph_state(mid_time) == "mid"

    assert search.timer_glyph_state(blank_timer()) == "absent"
    assert search.timer_glyph_state(np.full_like(blank_timer(), 255)) == "other"


def test_garage_exit_brackets_ignore_short_gaps_and_a_running_clock():
    samples = [
        (93.594, None, "absent"),
        (99.099, 0, "dashes"),
        (104.605, 0, "dashes"),
        (110.110, None, "running"),
        (115.615, 0, "running"),
        (200.0, None, "absent"),
        (950.0, None, "absent"),
        (952.452, 2, "dashes"),
        (1360.0, None, "absent"),
        (1365.364, 0, "running"),
    ]
    assert search.garage_exit_brackets(samples) == [(93.594, 99.099), (950.0, 952.452)]


def test_in_lap_brackets_skip_the_flying_lap_clock_reveal():
    flying = [(335.836, 368.868, 3)]
    samples = [
        (368.868, "long"),
        (374.374, "short"),
        (451.451, "long"),
        (456.957, "short"),
    ]
    assert search.is_flying_timer_reveal(374.374, flying) is True
    assert search.is_flying_timer_reveal(456.957, flying) is False
    assert search.in_lap_brackets(samples, flying) == [(451.451, 456.957)]
    assert search.in_lap_brackets([(90.0, "dashes"), (99.0, "short")], flying) == []


def test_timer_restart_needs_a_five_frame_hold_after_a_long_clock():
    frames = [(1.0, "long")]
    frames.extend((1.0 + index / 50, "short") for index in range(1, 5))
    assert search.timer_restart_time(frames) is None
    frames.append((1.1, "short"))
    assert search.timer_restart_time(frames) == 1.0 + 1 / 50
    assert search.timer_restart_time([(0.0, "short")] * 6) is None


def test_hot_lap_time_format():
    assert search.format_hot_lap_time(76.510) == "1:16.510"
    assert search.format_hot_lap_time(94.011) == "1:34.011"
    assert search.format_hot_lap_time(87.737) == "1:27.737"
    assert search.format_hot_lap_time(45.5) == "45.500"
    assert search.format_hot_lap_time(60) == "1:00.000"


def test_overlay_clock_replaces_a_near_video_gap_and_repairs_a_three():
    video_ms = 75_843
    assert search.parse_overlay_clock("1:15.840") == 75_840
    assert search.parse_overlay_clock("1:15.8409") == 75_840
    assert search.parse_overlay_clock("0.016") is None
    assert search.match_overlay_to_video(75_840, video_ms) == 75_840
    assert search.match_overlay_to_video(94_013, 94_011) == 94_013
    assert search.match_overlay_to_video(114_013, 94_011) == 94_013
    assert search.match_overlay_to_video(80_000, video_ms) is None
    assert search.choose_official_hot_lap_time(
        ["1:13.435", "1:15.840", "1:15.840", "0.016"],
        video_ms,
    ) == "1:15.840"
    assert search.choose_official_hot_lap_time(["1:54.013", "1:54.013"], 94_011) == "1:34.013"
    assert search.choose_official_hot_lap_time(["0.053", ""], video_ms) is None


def coloured(line):
    return f"{search.FASTEST_HOT_LAP_COLOUR}{line}{search.ANSI_RESET}"


def visible(line):
    return line.replace(search.FASTEST_HOT_LAP_COLOUR, "").replace(search.ANSI_RESET, "")


def test_first_stint_classification_keeps_the_in_lap_off_the_flying_starts():
    flying = [194.277, 270.787, 364.798]
    entries = search.classify_finished_laps(flying, [95.762], [452.535])
    assert entries == [
        ("out lap", 95.762),
        ("1:16.510", 194.277),
        ("1:34.011", 270.787),
        ("1:27.737", 364.798),
        ("in lap", 452.535),
    ]
    assert search.format_lap_report(entries) == [
        "out lap            1:35.762 ( 95.762)",
        coloured("hot lap  1:16.510  3:14.277 (194.277)"),
        "hot lap  1:34.011  4:30.787 (270.787)",
        "hot lap  1:27.737  6:04.798 (364.798)",
        "in lap             7:32.535 (452.535)",
    ]
    assert 452.535 not in flying


def test_lap_report_time_column_stays_blank_and_keeps_the_index_aligned():
    short_times = search.format_lap_report([("out lap", 1.0), ("45.500", 2.5), ("in lap", 3.0)])
    assert short_times == [
        "out lap            0:01.000 (1.000)",
        coloured("hot lap  45.500    0:02.500 (2.500)"),
        "in lap             0:03.000 (3.000)",
    ]
    long_time = search.format_lap_report([("out lap", 1.0), ("10:00.000", 2.0), ("in lap", 3.0)])
    assert long_time == [
        "out lap             0:01.000 (1.000)",
        coloured("hot lap  10:00.000  0:02.000 (2.000)"),
        "in lap              0:03.000 (3.000)",
    ]
    visible_lines = [visible(line) for line in long_time]
    assert (
        visible_lines[0].index("0:01.000 (1.000)")
        == visible_lines[1].index("0:02.000 (2.000)")
        == visible_lines[2].index("0:03.000 (3.000)")
    )


def test_tied_fastest_hot_laps_are_both_coloured():
    report = search.format_lap_report([("1:16.510", 10.0), ("1:20.000", 90.0), ("1:16.510", 180.0)])
    assert report[0] == coloured("hot lap  1:16.510  0:10.000 ( 10.000)")
    assert report[1] == "hot lap  1:20.000  1:30.000 ( 90.000)"
    assert report[2] == coloured("hot lap  1:16.510  3:00.000 (180.000)")


def test_lap_report_with_no_finished_laps_is_empty():
    assert search.format_lap_report([]) == []


def test_hot_lap_time_follows_the_printed_time_indexes():
    start = 364.7976
    end = 452.5354
    assert f"{start:.3f}" == "364.798"
    assert f"{end:.3f}" == "452.535"
    assert search.classify_finished_laps([start], [], [end]) == [
        ("1:27.737", start),
        ("in lap", end),
    ]


def test_later_stint_can_open_on_lap_two():
    entries = search.classify_finished_laps([1044.860], [950.0], [1135.085])
    assert entries == [
        ("out lap", 950.0),
        ("1:30.225", 1044.860),
        ("in lap", 1135.085),
    ]


def test_an_unfinished_hot_lap_is_omitted():
    entries = search.classify_finished_laps([3075.472], [2980.0], [])
    assert entries == [("out lap", 2980.0)]


def test_showinfo_pts_times_ignores_other_lines():
    stderr = "\n".join([
        "frame=1 fps=0.0",
        "[Parsed_showinfo_1 @ 0x1] n:   0 pts:  100 pts_time:280.78 duration: 1001",
        "side data pts_time:1.0",
        "[Parsed_showinfo_1 @ 0x1] n:   1 pts_time:374.37",
    ])
    assert search.showinfo_pts_times(stderr) == [280.78, 374.37]


def test_counter_crop_contains_the_qualifying_lap_label():
    assert search.counter_crop_for_frame(1920, 1080) == (220, 28, 100, 128)
    letter_box, digit_box = search.quali_boxes_in_counter_crop(1920, 1080)
    assert letter_box == (65, 0, 52, 28)
    assert digit_box == (116, 0, 24, 28)
    crop_width, crop_height, _x, _y = search.counter_crop_for_frame(1920, 1080)
    for box in (letter_box, digit_box):
        x, y, width, height = box
        assert x >= 0 and y >= 0
        assert x + width <= crop_width
        assert y + height <= crop_height


def test_race_digit_templates_match_themselves_and_stay_apart():
    for digit in range(10):
        template = search.race_digit_template(digit)
        assert template.shape == (search.RACE_DIGIT_CANVAS_HEIGHT, search.RACE_DIGIT_CANVAS_WIDTH)
        assert search.match_race_digit(template) == digit
    closest = 999
    for left in range(10):
        for right in range(left + 1, 10):
            distance = search.lap_digit_distance(
                search.race_digit_template(left), search.race_digit_template(right),
            )
            closest = min(closest, distance)
    assert closest >= search.RACE_DIGIT_MATCH_MARGIN


def tight_race_glyph(digit):
    template = search.race_digit_template(digit)
    rows, columns = np.where(template)
    return template[rows.min():rows.max() + 1, columns.min():columns.max() + 1]


def paint_glyph(image, glyph, x, y):
    height, width = glyph.shape
    image[y:y + height, x:x + width][glyph] = 255


def race_counter_image(digits):
    image = np.zeros((search.RACE_COUNTER_HEIGHT, search.RACE_COUNTER_WIDTH), dtype=np.uint8)
    x = 40
    y = 4
    for digit in digits:
        glyph = tight_race_glyph(digit)
        paint_glyph(image, glyph, x, y)
        x += glyph.shape[1] + 6
    image[9:19, x:x + 2] = 255
    image[10:20, x + 16:x + 32] = 255
    return image


def test_race_counter_reads_one_digit_and_two_digits():
    assert search.read_race_counter(race_counter_image([1])) == ("lap", 1)
    assert search.read_race_counter(race_counter_image([1, 2])) == ("lap", 12)
    assert search.read_race_counter(race_counter_image([3, 9])) == ("lap", 39)


def test_race_counter_ignores_a_digit_with_no_total():
    image = np.zeros((search.RACE_COUNTER_HEIGHT, search.RACE_COUNTER_WIDTH), dtype=np.uint8)
    paint_glyph(image, tight_race_glyph(1), 40, 4)
    assert search.read_race_counter(image) is None


def test_formation_banner_is_wide_lettering_without_a_lap_digit():
    banner = np.zeros((search.RACE_COUNTER_HEIGHT, search.RACE_COUNTER_WIDTH), dtype=np.uint8)
    for x in range(20, 180, 12):
        banner[8:20, x:x + 3] = 255
    assert search.read_race_counter(banner) == ("formation",)
    assert search.read_race_counter(np.zeros_like(banner)) is None
    short = np.zeros_like(banner)
    short[8:20, 20:60] = 255
    assert search.read_race_counter(short) is None


def test_race_session_needs_several_lap_reads():
    lap = ("lap", 4)
    short = [(float(index), lap) for index in range(search.RACE_MIN_LAP_READS - 1)]
    assert search.is_race_session(short) is False
    assert search.is_race_session(short + [(20.0, lap)]) is True
    formation_only = [(float(index), ("formation",)) for index in range(30)]
    assert search.is_race_session(formation_only) is False


def test_race_change_brackets_skip_replays_and_keep_the_formation_start():
    samples = [
        (1.0, None),
        (10.0, ("formation",)),
        (20.0, ("formation",)),
        (30.0, ("lap", 1)),
        (40.0, ("lap", 1)),
        (50.0, ("lap", 2)),
        (80.0, ("lap", 1)),
        (90.0, ("lap", 3)),
    ]
    assert search.race_change_brackets(samples) == [
        (1.0, 10.0, 0, False),
        (20.0, 30.0, 0, True),
        (40.0, 50.0, 1, True),
        (50.0, 90.0, 2, True),
    ]


def test_advancing_race_holds_emit_formation_then_each_new_lap():
    frames = [(0.1 * index, ("formation",)) for index in range(search.LAP_DIGIT_HOLD_FRAMES)]
    frames.extend(
        (1.0 + 0.1 * index, ("lap", 1)) for index in range(search.LAP_DIGIT_HOLD_FRAMES)
    )
    frames.append((2.0, ("lap", 2)))
    assert search.advancing_race_holds(frames, 0, False) == [
        (0.0, "formation"),
        (1.0, 1),
    ]


def test_window_opens_inside_the_screen():
    assert search.window_origin(960, 680, 1440, 900, 0) == (40, 48)
    x, y = search.window_origin(960, 680, 1000, 700, 0)
    assert 0 <= x <= 1000 - 960
    assert y == 0
    cascaded_x, cascaded_y = search.window_origin(960, 680, 1440, 900, search.WINDOW_CASCADE_SLOTS + 1)
    assert cascaded_x == 40 + search.WINDOW_CASCADE_STEP
    assert cascaded_y == 48 + search.WINDOW_CASCADE_STEP


def test_index_progress_names_the_stage():
    assert search.index_progress_message(3, 40, "Finding lap changes") == "Finding lap changes… 3/40"
    assert search.index_progress_message(0, None, "Finding the red lights") == "Finding the red lights…"


def test_red_light_search_looks_back_from_the_clock_start():
    assert search.red_light_search_span(349.5, 355.705) == (
        355.705 - search.RED_LIGHT_LOOKBACK_SECONDS,
        355.705 + search.RED_LIGHT_AFTER_SECONDS,
    )
    assert search.red_light_search_span(349.5, None) == (
        349.5,
        349.5 + search.RACE_LIGHTS_LOOKAHEAD_SECONDS,
    )


def test_red_light_drop_keeps_the_last_lit_frame():
    peak = 0.75
    still_lit = 0.74
    dropped = 0.20
    scores = [peak, still_lit, dropped, dropped]
    assert search.is_significant_red_drop(still_lit, peak) is False
    assert search.is_significant_red_drop(dropped, peak) is True
    assert search.red_light_drop(scores) == (1, 2)
    assert search.red_light_drop([peak, dropped, still_lit]) == (0, None)


def test_lights_search_window_runs_from_the_formation_lap_to_lap_one():
    events = [
        (214.931, "formation"),
        (355.705, 1),
        (440.240, 2),
    ]
    assert search.lights_search_window(events) == (214.931, 355.705)
    assert search.lights_search_window([(214.931, "formation")]) is None
    assert search.lights_search_window([(355.705, 1)]) is None
    assert search.lights_search_window([(400.0, "formation"), (355.705, 1)]) is None


def test_running_clock_starts_after_the_grid_dashes():
    frames = [(0.0, "dashes"), (0.1, "long")]
    frames.extend((0.2 + index / 50, "short") for index in range(search.LAP_DIGIT_HOLD_FRAMES))
    assert search.running_clock_time(frames) == 0.2
    assert search.running_clock_time([(0.0, "short")] * search.LAP_DIGIT_HOLD_FRAMES) is None
    frames = [(0.0, "dashes")]
    frames.extend((0.1 + index / 50, "short") for index in range(search.LAP_DIGIT_HOLD_FRAMES - 1))
    assert search.running_clock_time(frames) is None


def test_race_lap_report_lines_up_the_formation_lap_and_colours_the_fastest():
    rows = [
        ("formation", "", 220.220, 352.352),
        ("lap  1", "1:18.000", 352.352, 430.352),
        ("lap  2", "1:16.000", 430.352, None),
    ]
    report = search.format_race_lap_report(rows)
    visible_lines = [visible(line) for line in report]
    assert visible_lines == [
        "formation            3:40.220 (220.220)",
        "lap  1     1:18.000  5:52.352 (352.352)",
        "lap  2     1:16.000  7:10.352 (430.352)",
    ]
    assert (
        visible_lines[0].index("3:40.220 (220.220)")
        == visible_lines[1].index("5:52.352 (352.352)")
        == visible_lines[2].index("7:10.352 (430.352)")
    )
    assert report[1] == visible(report[1])
    assert report[2] == coloured(visible(report[2]))
