from os import system, path, listdir
from shutil import copy, copyfileobj, move
from subprocess import check_output

# Constants
EMPTY_DIR = 0
MIN_FILE_LEN = 4
DOT_CFG = 4
MNT_SUBFOLDER = 5
VOLID_START = 11


# RHEL 9 configuration manager.
## Creates a custom RHEL9 ISO with a .ks file
### The .ks handles package installation, partitioning, addons (e.g. disabling kdump), etc. 
## Additionally, packages this .ks with a custom Ansible pull %post script that handles STIG tasks and other setup that must be done after installation.
def main() -> int:
    # 1. Setup: unpack an existing ISO, and use the working directory of its files. 
    # Alternatively, select a working directory with copied disc files.
    mount_sel = ""
    perm_loc = ""
    iso_loc = ""
    while mount_sel != 'n' and mount_sel != 'y':
        mount_sel = input("Enter 'y' to unpack an .iso file, or 'n' to select an existing unpacked working directory: ").strip().lower()
    if mount_sel == 'y':
        iso_tup = mount_iso()
        iso_loc = iso_tup[0]
        mnt_loc = iso_tup[1]
        perm_loc = copy_files(mnt_loc) + "/" + mnt_loc[MNT_SUBFOLDER:]
        if perm_loc[len(perm_loc) - 1:] != "/":
            perm_loc += "/"
    else:
        while not path.isdir(perm_loc) or perm_loc[0] != "/":
            perm_loc = input("Enter the path to the disc files (must be absolute): ").strip()
        if perm_loc[len(perm_loc) - 1:] != "/":
            perm_loc += "/"
        
        while not path.isfile(iso_loc) and iso_loc[len(iso_loc) - MIN_FILE_LEN:] != ".iso":
            iso_loc = input("Enter the location of the original .iso file: ").strip()

    # 2. Select an existing ks, or configure one. Add this to the ISO, and add the inst.ks option where it is needed.
    select_ks(perm_loc)
    edit_grub(perm_loc)
    
    # 3. Optionally, append a %post script that pulls from a remote repo and performs an Ansible pull to take care of other tasks.
    post_sel = ""
    while post_sel != 'n' and post_sel != 'y':
        post_sel = input("Enter 'y' to add a %post script, or 'n' to continue and rebuild: ").strip().lower()
    if post_sel == 'y':
        append_ans(perm_loc)

    # 4. Package this iso and finish. 
    pack_new_iso(iso_loc, perm_loc)
    return 0


# Mount the iso, then copy its contents to a location and unmount.
# Returns the mount location.
def mount_iso() -> tuple:
    # Get iso location.
    iso_location = ""
    while not path.isfile(iso_location) or len(iso_location) <= MIN_FILE_LEN or iso_location[len(iso_location) - MIN_FILE_LEN:] != ".iso" or iso_location[0] != "/":
        iso_location = input("Enter the location of the .iso file to unpack: ").strip()
        if not path.isfile(iso_location) or len(iso_location) <= MIN_FILE_LEN or iso_location[len(iso_location) - MIN_FILE_LEN:] != ".iso":
            print("File does not exist, or is not an .iso file.")

    # Get mount path.
    mnt_path = ""
    while not path.isdir(mnt_path) or len(listdir(mnt_path)) > EMPTY_DIR or path.ismount(mnt_path):
        mnt_path = ("/mnt/" + input("Enter a temporary location in /mnt/ to mount your ISO (must exist): ")).strip()
        if path.ismount(mnt_path):
            print("Path is already mounted to.")
        elif not path.isdir(mnt_path) or len(listdir(mnt_path)) > EMPTY_DIR:
            print("Path does not exist or is not empty.")
    
    # Mount. Return the mount location.
    system(f"mount {iso_location} {mnt_path}")
    return (iso_location, mnt_path)


# Copy the unpacked files to a permanent location. Unmount the iso.
# Return the location of the copied files.
def copy_files(mnt_loc: str) -> str:
    # Get permanent location.
    perm_loc = ""
    while not path.isdir(perm_loc) or len(listdir(perm_loc)) > EMPTY_DIR or perm_loc[0] != "/":
        perm_loc = input("Enter the location to copy the unpacked .iso to (must be empty and absolute): ").strip()
        if not path.isdir(perm_loc) or len(listdir(perm_loc)) > EMPTY_DIR or perm_loc[0] != "/":
            print("Path is not a directory, is not absolute, or is not empty.")
    
    # Unmount mnt_loc, copy files, return permanent location.
    system(f"rsync -av {mnt_loc} {perm_loc}")
    print(f"Finished copying. Unmounting {mnt_loc}...")
    system(f"umount {mnt_loc}")
    return perm_loc


# Select a kickstart from the kickstart folder, or input the location of one.
# Copy this kickstart to the unpacked iso location. 
def select_ks(perm_loc: str) -> None:
    # Print ks files, get selection. 
    print("Included kickstart files:")
    i = 1
    for filename in listdir("./kickstarts/"):
        print(i, ". ", filename)
        i += 1

    # Verify selection. Move this file to the rootdir of the iso.
    ks_sel = ""
    while ks_sel == "":
        print("Select a kickstart from one of the available configurations or enter in the location of your kickstart file.")
        try:
            ks_sel = input("Selection: ")
            ks_int = int(ks_sel)
            if ks_int <= 0 or ks_int > len(listdir("./kickstarts/")):
                ks_sel = ""
                print("Out of range selection.")
            else:
                ks_sel = "./kickstarts/" + listdir("./kickstarts/")[ks_int - 1]
        except ValueError:
            if not path.isfile(ks_sel) or ks_sel[len(ks_sel) - DOT_CFG:] != ".cfg":
                ks_sel = ""
                print("Path does not exist or is not a .cfg file.")
    
    print(f"Selected {ks_sel}; moving to iso root.")
    copy(ks_sel, f"{perm_loc}ks.cfg")


# Add the necessary kickstart boot options to the GRUB menu files
def edit_grub(root_loc: str) -> None:
    # Add inst.ks option to isolinux.cfg
    temp = open("./temp", 'w')
    with open(f"{root_loc}isolinux/isolinux.cfg") as isolinux:
        for line in isolinux:
            if line.strip().startswith("append"):
                line = line.rstrip() + " inst.ks=cdrom:/ks.cfg\n"
                print("Added inst.ks option to isolinux.cfg.")
            temp.write(line)
    temp.close()
    move("./temp", f"{root_loc}isolinux/isolinux.cfg")

    # And to grub.cfg
    temp = open("temp", 'w')
    with open(f"{root_loc}EFI/BOOT/grub.cfg") as grub:
        for line in grub:
            if line.strip().startswith("linuxefi"):
                line = line.rstrip() + " inst.ks=cdrom:/ks.cfg\n"
                print("Added inst.ks option to grub.cfg.")
            temp.write(line)
    temp.close()
    move("./temp", f"{root_loc}EFI/BOOT/grub.cfg")


# Add an Ansible playbook pull to the %post section from a remote repository.
# Alternatively, select a playbook/repo that is already available.
def append_ans(perm_loc: str) -> None:
    # Print scripts.
    print("Included post scripts:")
    i = 1
    for filename in listdir("./postscripts/"):
        print(i, ". ", filename)
        i += 1
    
    # Verify selection and copyfileobj to the end of the .ks
    # Verify selection. Move this file to the rootdir of the iso.
    script_sel = ""
    while script_sel == "":
        print("Select a script from one of the available selections or enter in a file location.")
        try:
            script_sel = input("Selection: ")
            script_int = int(script_sel)
            if script_int <= 0 or script_int > len(listdir("./postscripts/")):
                script_sel = ""
                print("Out of range selection.")
            else:
                script_sel = "./postscripts/" + listdir("./postscripts/")[script_int - 1]
        except ValueError:
            if not path.isfile(script_sel):
                script_sel = ""
                print("Path does not exist or is not a .cfg file.")
    
    # Append script to ks 
    print(f"Selected {script_sel}; appended to kickstart.")
    with open(f"{perm_loc}ks.cfg", 'a') as kickstart:
        with open(script_sel, 'r') as postscript:
            copyfileobj(postscript, kickstart)


# Repackage this iso using xorriso. Downloads necessary dependencies, if required. 
def pack_new_iso(iso_loc: str, root_loc: str) -> None:
    print("Verifying xorriso...")
    system("sudo apt install xorriso")

    print("Verifying isolinux...")
    system("sudo apt install isolinux")

    print("Verifying genisoimage...")
    system("sudo apt install genisoimage")

    # Find correct volume name - new iso will be broken if this is incorrect.
    print("Getting volume name...")
    vol_cmd = f"isoinfo -d -i {iso_loc} | grep 'Volume id'"
    vol_name = check_output(vol_cmd, shell=True, text=True)[VOLID_START:].strip()

    # Binary required for xorriso command.
    print("Locating isohdpfx.bin...")
    isohdpfx_loc = check_output("dpkg -L isolinux | grep isohdpfx.bin", shell=True, text=True).strip()

    output_loc = ""
    while not path.isdir(output_loc):
        output_loc = input("Enter a location for the output .iso (must be absolute and exist): ").strip()
        if not path.isdir(output_loc) or output_loc[0] != "/":
            print("Path does not exist or is not absolute.")
    
    system_call = (f'xorriso -as mkisofs -iso-level 3 -full-iso9660-filenames -volid "{vol_name}" -eltorito-boot ' 
           f'isolinux/isolinux.bin -eltorito-catalog isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table '
           f'-isohybrid-mbr {isohdpfx_loc} -eltorito-alt-boot -e images/efiboot.img -no-emul-boot -isohybrid-gpt-basdat '
           f'-output {output_loc}ks.iso -graft-points {root_loc}')
    system(system_call)


if __name__ == "__main__":
    main()
