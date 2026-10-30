import numpy as np

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
