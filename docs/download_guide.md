# MSC download guide

We do not redistribute the source videos (copyright). This table documents,
per movie, the specific commercial release our own copy corresponds to
(identified via the BBFC cross-check, see `docs/methodology.md`) and a
reference SHA-256 checksum, so you can confirm a release you have sourced
independently is equivalent before trusting our shot/scene boundaries
(`MSC/shots_trust.csv` / `MSC/scenes_trust.csv`) against it.

A checksum match means byte-identical files. A mismatch does not
necessarily mean incompatibility -- re-encodes/remuxes of the same cut
commonly change the checksum without changing frame content -- but it does
mean you should spot-check against `MSC/verification_frames/` before
assuming alignment with `shots_trust.csv`/`scenes_trust.csv`.

| Movie | IMDb ID | Matched release (BBFC) | Expected filename | SHA-256 |
|---|---|---|---|---|
| 12 Monkeys | tt0114746 | Cinema, 2015 | `Twelve_Monkeys_1995.mp4` | `cbec2245f32594f15dd1c8f66b0f1ef7c1cab7eccc7a25ceb9f354cf1f8c3c04` |
| 12 Years a Slave | tt2024544 | Cinema, 2013 | `12_Years_a_Slave_2013.mp4` | `21cd851a76a8b8686b8b632e4b2de86918238cc9f68e5436c6e5131f16804a96` |
| Apocalypse Now | tt0078788 | Redux, HE, 2002 | `Apocalypse_Now_1979.mp4` | `ce3158939c0ef17d12ad4c38344db8a1604cf62b8c2960ae25387d54c91b712e` |
| Batman Returns | tt0103776 | Cinema, 2019 | `Batman_Returns_1992.mp4` | `3f9293ad21e26012bcd4e3ac395a81f38e90feab4fdbe2774d199f0b13f7ec8d` |
| Body Heat | tt0082089 | Cinema, 1981 | `Body_Heat_1981.mp4` | `a08e53b3abf12158738f6befe67df6253e8cff5895ce5a19e324315bdc17c283` |
| Braveheart | tt0112573 | Cinema, 1995 | `Braveheart_1995.mp4` | `514458e689fcc0e7c9879be446567722832454f35d6fb08b25ebb364329876ec` |
| Broken Arrow | tt0115759 | Cinema, 1996 | `Broken_Arrow_1996.mp4` | `5b1b8b9b9e6906e603c7a0073a903e50b6bb8eb3538e4c06db9e24912d30af29` |
| Commando | tt0088944 | Cinema, 1985 | `Commando_1985.mp4` | `b76006707af4343e6bbac27544aed5b9f9b772f240df4433838c1cec95e2c39a` |
| Crank | tt0479884 | Cinema, 2006 | `Crank_2006.mp4` | `2bcee64f7fd8926ae118fee6ea92414753d3c40e6a2f777d8f9ede24909105bf` |
| Crouching Tiger, Hidden Dragon | tt0190332 | Cinema, 2000 | `Crouching_Tiger_Hidden_Dragon_2000.mp4` | `032310933cc9f54ef6b5cec49da244855092d0065e1cf0d5d87a4989377706c0` |
| Cube | tt0123755 | Cinema, 1998 | `Cube_1997.mp4` | `f011a8b7471dd0646fd1e19d5e52275abe046a0a36f57130d5994fa07ccf4d38` |
| Fargo | tt0116282 | Cinema, 1996 | `Fargo_1996.mkv` | `61d1d4c124d7c23f289c02c078006de53632596167aa599e44f46bfbce78e6dc` |
| Fight Club | tt0137523 | Cinema, 2014 | `Fight_Club_1999.mp4` | `70e5649559dde29edce8b48ee4fa73ca81e1b00eed9dcda5619840ccb838365d` |
| Gangs of New York | tt0217505 | Cinema, 2023 | `Gangs_of_New_York_2002.mp4` | `ed37e225e6e4d3dcab6376263a021aedfa540e2f2df0756c4a9aa6b45b39435f` |
| Gran Torino | tt1205489 | Cinema, 2008 | `Gran_Torino_2008.mp4` | `f7764345636b2896635c904445846cc3410262ca8bbc74c9035a021a79bc13c4` |
| He's Just Not That Into You | tt1001508 | Cinema, 2009 | `Hes_Just_Not_That_Into_You_2009.mp4` | `139b24d507cd3fd14411291a2fed493e1da8cb1b66c6f64439ce239173890283` |
| Heat | tt0113277 | Other, 2016 | `Heat_1995.mkv` | `f4cd47dfc69f70474ca7c581c339cc7bdbb9c08232c5199a13198d8a851d3ab2` |
| Inception | tt1375666 | Cinema, 2010 | `Inception_2010.mkv` | `df96895ef607efcc3ef780da4c00a86929720659eaabbd442c36f02dc40562f1` |
| Inglourious Basterds | tt0361748 | Cinema, 2009 | `Inglourious_Basterds_2009.mp4` | `de2250510a0c0ea01cb5397ff0309639b5b077d56c4999fd4ff7c488b76cf19b` |
| Jaws | tt0073195 | Cinema, 2022 | `Jaws_1975.mp4` | `d6d4e3bad48ff5aa881755db000140da7721392346f0fdc09294db5737be016e` |
| Jurassic Park | tt0107290 | Cinema, 1993 | `Jurassic_Park_1993.mp4` | `4d2373da68ff78180527de68d964ae6a00627d01173db46b863200454122d8d0` |
| Jurassic Park III | tt0163025 | Cinema, 2001 | `Jurassic_Park_III_2001.mp4` | `73b94fcec3f5c14f4035b91097ac32405128e5ccee9dac4bb4d50c8ec96ed4fb` |
| L.A. Confidential | tt0119488 | Cinema, 1997 | `L_A_Confidential_1997.mkv` | `a857945d953e07d3d6e01fbb24fc9ed9017dd1d9930bf3c6be42006936d1b8a1` |
| Les Misérables | tt1707386 | Cinema, 2012 | `Les_Miserables_2012.mp4` | `4ba7418037a1b52cd4959c8fb41de936c588a2ebdfe32f86cd02b7e8ff336f4f` |
| Lincoln | tt0443272 | Cinema, 2012 | `Lincoln_2012.mp4` | `65fc8bbd01b7696d6864b5ffed3af700746ad217b2644dcc64a3143ed968ac30` |
| Marley & Me | tt0822832 | Cinema, 2008 | `Marley_and_Me_2008.mp4` | `1fd76143896032175828754350aeaa4dd470b6602335ab1d4db72eee314fdbfb` |
| Mission: Impossible | tt0117060 | Cinema, 2015 | `Mission_Impossible_1996.mp4` | `2f38afec0e2c21e0e1709588722d260f4cc57281e0ee58c7974dea275cd08fb0` |
| Mr. Brooks | tt0780571 | Cinema, 2007 | `Mr_Brooks_2007.mp4` | `ec9b6ab227eea8b8bb65083d9b4df884d52a921665d5ab958106dc4162922a45` |
| Mute Witness | tt0110604 | Cinema, 1995 | `Mute_Witness_1995_b.mkv` | `8dd3e3bd16c144ca83bbf818e29e6777a0e1a91063f1cf7d5c40881912381a85` |
| Planet of the Apes | tt0063442 | Cinema, 1968 | `Planet_Of_The_Apes_1968.mp4` | `9cf81854926c0c40196398ad87fd8908d4c344e3aed60102d9295fbc70eb05fd` |
| Pretty Woman | tt0100405 | Cinema, 1990 | `Pretty_Woman_1990.mp4` | `9354799a61ff809aa6906fe48431d28ba4f241472be84fb09817a981cdb05f3b` |
| Ring | tt0178868 | Cinema, 2000 | `Ringu_1998.mkv` | `bd8bd067b6e27bcb038d3cedf6558db799d4b6b431afd6121197c0b57fe84608` |
| Serenity | tt0379786 | HE, 2006 | `Serenity_2005.mkv` | `90d26339613010a7d26e5f8e48f4bd75c1fafa5e9af27836ca18c92d0a85ead2` |
| Source Code | tt0945513 | Cinema, 2011 | `Source_Code_2011.mp4` | `ef9b1400cb69e7fea1cf7d49a1b045b3384b0af357a9f82d9492dfa6a281ebba` |
| The Best Exotic Marigold Hotel | tt1412386 | Cinema, 2012 | `The_Best_Exotic_Marigold_Hotel_2011.mp4` | `8e63ece4e5ad8827f272317d767cdbca0ace334bc6da5bebdae5d7943f0a53ea` |
| The Big Lebowski | tt0118715 | Cinema, 1998 | `The_Big_Lebowski_1998.mp4` | `39ec4793acb84a48e1816815427ccf1d36e430c0a9c65b55b1deeb151cfe3509` |
| The Bodyguard | tt0103855 | Cinema, 1992 | `The_Bodyguard_1992.mp4` | `105c68c5d2846eba9b1a26342b4ad754676ea375f6ad65d3805551864bae2935` |
| The Bounty Hunter | tt1038919 | Cinema, 2010 | `The_Bounty_Hunter_2010.mp4` | `0dbbcf9bf893809a02030aa650d961d6550ad081a1df81ddf2efcf0977556689` |
| The Bourne Ultimatum | tt0440963 | Cinema, 2007 | `The_Bourne_Ultimatum_2007.mp4` | `76e1ec0e5ed7b66df6732e29566dd4372139b3f0979b9ce739034553539a7e5e` |
| The Cider House Rules | tt0124315 | Cinema, 2000 | `The_Cider_House_Rules_1999.mp4` | `2b28a8bcb37d8ac1b6cb70384c149ca43c7bfd8f5f8abec793e1f77390bb2eef` |
| The Fault in Our Stars | tt2582846 | Other, 2014 | `The_Fault_in_Our_Stars_2014.mp4` | `c4a63865eb9c216e8642de96ede5382270873474ab9508689c672a3c32aa16d8` |
| The Godfather | tt0068646 | Cinema, 1996 | `The_Godfather_1972.mp4` | `50d25dd77450b48fb6ed1844e4d4db2fb8d12cd75ddac6714c779f4262dfb470` |
| The Green Mile | tt0120689 | Other, 2014 | `The_Green_Mile_1999.mp4` | `5954c155bb444513d66dc7d3b5bfe05fc3b072b723d6910e6d7322e7eb0e6ca0` |
| The Hangover | tt1119646 | HE, 2009 | `The_Hangover_2009.mp4` | `716d8a4b99fa607f9062ff125c5d6bcaaf2a1d3a8c0b820b69e6cd18ed79ddfd` |
| The Island | tt0399201 | Cinema, 2005 | `The_Island_2005.mp4` | `4919c58cbcfc2135f6291bb34a41abf11c520ef5b236465b76d0bfe4b08af884` |
| The Pianist | tt0253474 | Cinema, 2002 | `The_Pianist_2002.mp4` | `1f594e3252c08d47cfce877eec2eca09dff7bc3a3d4ecaa93b0437eb0c450098` |
| The Reader | tt0976051 | Cinema, 2008 | `The_Reader_2008.mp4` | `45ce7d76618a546114058e0db8a8f2d79cc97a9cd6417c4e561ddd92c12f2779` |
| The Terminator | tt0088247 | Cinema, 1984 | `The_Terminator_1984.mp4` | `13c6819ea5af7735ce69c64b31fb314864b5fb9763423b3afb55776e2bf71069` |
| The Truman Show | tt0120382 | Cinema, 1998 | `The_Truman_Show_1998.mkv` | `93116a08ab587f816ed37c0264832ca7d3d6a7e70cfd5051d1997a9dc18d2da6` |
| Top Gun | tt0092099 | Cinema, 2026 | `Top_Gun_1986.mp4` | `d43d66fd8eaab2ea229de3dff78bdc46de683ba503929b58081882ffc44678da` |
| Twilight | tt1099212 | Cinema, 2008 | `Twilight_Saga_2008.mp4` | `f5871785b1bc1dd8a037a1134161ca0529a264094eaf79358254e30327e6f252` |
| Twins | tt0096320 | Cinema, 1988 | `Twins_1988.mp4` | `25e967429645b31bbf4272ab37dff514992a36afa9bc8f2b2e08256eabe2ad56` |
| Vertigo | tt0052357 | Cinema, 2012 | `Vertigo_1958.mp4` | `6ac6a83041fcce28bca59d4c2b53590dacb124d21e6cd31485da9526bde4c6a4` |
| Wild Things | tt0120890 | HE, 2023 | `Wild_Things_1998.mp4` | `eb84edb26e40907bb11e196d1804414b9d7e697d38210822061f5470553400cf` |
