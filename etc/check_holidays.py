from functools import partial

import click
import pandas as pd

from trading_calendars import get_calendar
from trading_calendars.calendar_utils import default_calendar_names


class TimestampType(click.ParamType):
    """A click parameter that parses the value into pandas.Timestamp objects.

    Parameters
    ----------
    tz : timezone-coercable, optional
        The timezone to parse the string as.
        By default the timezone will be infered from the string or naiive.
    """
    def __init__(self, tz=None):
        self.tz = tz

    @property
    def name(self):
        return 'TIMESTAMP'

    def convert(self, value, param, ctx):
        try:
            return pd.Timestamp(value, tz=self.tz)
        except ValueError:
            self.fail(
                '%s is not a valid timestamp.' % value,
                param,
                ctx,
            )


def check_holidays(holiday_key_path,
                   calendar_column,
                   holiday_column,
                   date_format,
                   delimiter,
                   strip_x_from_cal_name,
                   min_date,
                   calendars):
    data = pd.read_csv(
        holiday_key_path,
        sep=delimiter,
        parse_dates=[holiday_column],
        date_parser=partial(pd.to_datetime, format=date_format, utc=True)
    )

    for calendar_name in default_calendar_names:
        if calendars and calendar_name not in calendars:
            continue

        cal = get_calendar(calendar_name)

        # Convert the calendar name to the format expected in the CSV.
        if strip_x_from_cal_name:
            csv_cal_code = calendar_name.lstrip('X')
        else:
            csv_cal_code = calendar_name

        holidays = set(
            data[holiday_column][
                data[calendar_column] == csv_cal_code
            ]
        )

        if holidays:
            start = max(cal.first_session, min(holidays), min_date)
            end = min(cal.last_session, max(holidays))

            _check_range(start, end, holidays, cal, calendar_name)
        else:
            click.secho(
                'No holidays found for {} in the holiday key.'.format(
                    calendar_name,
                ),
                fg='yellow',
            )

        click.echo()


def _check_range(start, end, holidays, cal, calendar_name):
    msg = (
        'Checking {} holidays on the {} ({}) calendar between {} and {}.'
    ).format(
        len(holidays),
        type(cal).__name__,
        calendar_name,
        start.date(),
        end.date(),
    )
    click.echo(msg)

    dates = pd.date_range(start, end, freq='B')

    expected_sessions = dates.difference(holidays)
    actual_sessions = cal.sessions_in_range(start, end)

    unexpected_sessions = actual_sessions.difference(expected_sessions)
    unexpected_holidays = expected_sessions.difference(actual_sessions)

    for session in unexpected_sessions:
        click.secho(
            (
                '{} is in the holiday key, but is a valid'
                ' session in the {} trading calendar.'
            ).format(
                session.date(),
                calendar_name,
            ),
            fg='red',
        )

    for holiday in unexpected_holidays:
        click.secho(
            (
                '{} is not in the holiday key, but is not a'
                ' valid session in the {} trading calendar.'
            ).format(
                holiday.date(),
                calendar_name,
            ),
            fg='red',
        )

    if not unexpected_sessions.size and not unexpected_holidays.size:
        click.secho(
            '{} calendar matches the holiday key.'.format(calendar_name),
            fg='green',
        )


@click.command(help=(
    'Checks trading calendars against a holiday key.'
    ' HOLIDAY_KEY_PATH is the path to a CSV file containing the key,'
    ' with a calendar name column and a holiday date column.'
))
@click.option(
    '--min-date',
    default=pd.Timestamp('2002-01-01'),
    type=TimestampType(tz='UTC'),
    help='Start the holiday comparison at this date.',
    show_default=True,
)
@click.option(
    '--calendar', 'calendars',
    multiple=True,
    type=click.Choice(default_calendar_names),
    help=(
        'The name of a calendar to check. Specify multiple times to'
        ' check multiple calendars. Default is to check all calendars.'
    ),
)
@click.option('--calendar-column', help='The calendar name column in the CSV.')
@click.option('--holiday-column', help='The holiday date column in the CSV.')
@click.option(
    '--date-format',
    default='%Y%m%d',
    help='strftime format string for parsing the date column.',
    show_default=True,
)
@click.option(
    '--delimiter',
    '--sep',
    default=',',
    help='Delimiter to use when parsing the key.',
    show_default=True,
)
@click.option(
    '--strip-x-from-cal-name/--no-strip-x-from-cal-name',
    help='E.g. "XNYS" is looked up in the key as "NYS".',
    show_default=True)
@click.argument('holiday_key_path', type=click.Path(exists=True))
def main(holiday_key_path,
         min_date,
         calendars,
         calendar_column,
         holiday_column,
         date_format,
         delimiter,
         strip_x_from_cal_name):

    check_holidays(
        holiday_key_path,
        calendar_column,
        holiday_column,
        date_format,
        delimiter,
        strip_x_from_cal_name,
        min_date,
        calendars,
    )


if __name__ == '__main__':
    main()
