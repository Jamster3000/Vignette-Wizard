# Vignette-Wizard

[Uploading icon.ico…]()

This python application is used to be given a folder path containing one or more images, modify any given settings including colour of the vignette, then press the button. The program will add a vignette to each images and save a copy in a new folder in the given original folder path. Tested out on images about 1.7 - 2 MB 2000x2000 size, it's taking any time from 0.4 - 0.8 seconds to process each image.

## Pyinstaller
I have used the following cmd command to build the exe application

```pyinstaller --clean -y --name "Vignette Wizard" --windowed --add-data "C:\Users\ThinkPad\AppData\Local\Programs\Python\Python311\Lib\site-packages\customtkinter;customtkinter/" --onefile -i "icon.ico" wizard.py```

![GitHub issues](https://img.shields.io/github/issues/jamster3000/Vignette-Wizard)
![Last Commit](https://img.shields.io/github/last-commit/jamster3000/Vignette-Wizard)
![GitHub Stars](https://img.shields.io/github/stars/jamster3000/Vignette-Wizard?style=social)![Code Size](https://img.shields.io/github/languages/code-size/jamster3000/Vignette-Wizard)
