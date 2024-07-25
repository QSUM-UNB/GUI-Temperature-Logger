# GUI-Temperature-Logger
A PyQt graphical user interface for temperature and humidity logging based on the Thorlabs TSP01B

## Requirements

First and foremost, the program only supports Windows. This is a limitation of the Thorlabs drivers.

You must have Python 3.10 installed. This can be obtained from [here.](https://python.org)

You must also make sure you have the following packages installed from PIP:

|Packages|
|--------|
|PyQt6|
|Matplotlib|
|numpy|
|scipy|

Finally, you must have the Thorlabs TSP01B drivers installed. This can be obtained from [here.](https://www.thorlabs.com/software_pages/viewsoftwarepage.cfm?code=TSP)

## Usage

The program can be run by double-clicking on `app.pyw`. You may also wish to run:

```sh
python3.10 app.py
```

You may also replace `python3.10` with whichever keyword you have bound to Python 3.10.

Once logging, the program must be kept open (though you may wish to minimize the window). On each new month, the program will automatically create a new file. Old data can be recalled at anytime and can be viewed in the Graph tab or in the Table tab. Analysis can also be performed after data has been loaded. A PSD will be performed as well as a Welch with a user-defined data split.

