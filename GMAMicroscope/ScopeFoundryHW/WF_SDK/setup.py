from setuptools import setup
 
with open("README.md", "r") as f:
    long_description = f.read()
 
setup(
   name = "WF_SDK",
   version = "1.0",
   description = "This module realizes communication with Digilent Test & Measurement devices",
   license = "MIT",
   long_description = long_description,
   author = "author_name",
   author_email = "author_email_address",
   url = "https://digilent.com/reference/test-and-measurement/guides/waveforms-sdk-getting-started",
   packages = ["WF_SDK", "WF_SDK.protocol"],
)