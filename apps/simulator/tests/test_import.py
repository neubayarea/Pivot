from pivot_simulator.__main__ import main


def test_main_runs(capsys):
    main()
    assert "pivot-simulator" in capsys.readouterr().out
